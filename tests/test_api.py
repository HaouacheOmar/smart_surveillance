from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from modules.authentication.models import User
from modules.cameras.models import Camera
from modules.monitoring.models import Checkout, Hallway, OccupancyLog
from modules.monitoring.services import DISPLAY_GROUP, ingest_metrics

SQUARE = [[0, 0], [1, 0], [1, 1]]


@override_settings(SERVICE_TOKEN="svc")
class ApiTests(TestCase):
    def setUp(self):
        User.objects.create_user("admin", password="pass-12345", role=User.Role.ADMIN)
        User.objects.create_user("op", password="pass-12345")
        self.client = APIClient(enforce_csrf_checks=True)

    def login(self, username="admin"):
        res = self.client.post("/api/auth/login/", {"username": username, "password": "pass-12345"}, format="json")
        self.assertEqual(res.status_code, 200)
        return {"HTTP_X_CSRFTOKEN": self.client.cookies["csrftoken"].value}

    def test_login_sets_httponly_cookies_and_bad_password_fails(self):
        res = self.client.post("/api/auth/login/", {"username": "admin", "password": "nope"}, format="json")
        self.assertEqual(res.status_code, 401)
        self.login()
        self.assertTrue(self.client.cookies["access_token"]["httponly"])
        self.assertTrue(self.client.cookies["refresh_token"]["httponly"])
        self.assertEqual(self.client.get("/api/auth/me/").data["username"], "admin")

    def test_unauthenticated_and_csrf(self):
        self.assertEqual(self.client.get("/api/cameras/").status_code, 401)
        self.login()
        body = {"name": "c", "ip_address": "10.0.0.1", "rtsp_url": "rtsp://10.0.0.1/s"}
        self.assertEqual(self.client.post("/api/cameras/", body, format="json").status_code, 403)  # no CSRF header

    def test_refresh_and_logout(self):
        self.login()
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 204)
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.post("/api/auth/refresh/").status_code, 401)

    def test_camera_password_is_encrypted_and_never_returned(self):
        csrf = self.login()
        body = {"name": "c", "ip_address": "10.0.0.1", "rtsp_url": "rtsp://10.0.0.1:554/s",
                "username": "u", "password": "p@ss/word"}
        res = self.client.post("/api/cameras/", body, format="json", **csrf)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotIn("password", res.data)
        cam = Camera.objects.get()
        self.assertNotIn("p@ss", cam.password_encrypted)
        self.assertEqual(cam.authenticated_rtsp_url, "rtsp://u:p%40ss%2Fword@10.0.0.1:554/s")
        bad = {**body, "rtsp_url": "rtsp://u:p@10.0.0.1/s"}
        self.assertEqual(self.client.post("/api/cameras/", bad, format="json", **csrf).status_code, 400)

    def test_operator_is_read_only(self):
        csrf = self.login("op")
        self.assertEqual(self.client.get("/api/cameras/").status_code, 200)
        body = {"name": "c", "ip_address": "10.0.0.1", "rtsp_url": "rtsp://10.0.0.1/s"}
        self.assertEqual(self.client.post("/api/cameras/", body, format="json", **csrf).status_code, 403)

    def test_ingest_updates_state_logs_changes_and_feeds_display(self):
        cam = Camera.objects.create(name="c", ip_address="10.0.0.1", rtsp_url="rtsp://10.0.0.1/s")
        other = Camera.objects.create(name="o", ip_address="10.0.0.2", rtsp_url="rtsp://10.0.0.2/s")
        hall = Hallway.objects.create(camera=cam, name="H1", polygon=SQUARE)
        co = Checkout.objects.create(hallway=hall, name="C1", polygon=SQUARE)
        foreign = Hallway.objects.create(camera=other, name="H2", polygon=SQUARE)

        payload = {"camera_id": cam.id, "hallways": {str(hall.id): 4, str(foreign.id): 9},
                   "checkouts": {str(co.id): True}, "open": {str(co.id): False}}
        self.assertEqual(self.client.post("/api/internal/ingest/", payload, format="json").status_code, 403)
        for _ in range(2):  # second tick is identical -> no new log row
            res = self.client.post("/api/internal/ingest/", payload, format="json", HTTP_X_SERVICE_TOKEN="svc")
            self.assertEqual(res.status_code, 204)

        hall.refresh_from_db(), co.refresh_from_db(), foreign.refresh_from_db()
        self.assertEqual((hall.people_count, co.is_occupied, co.is_open, foreign.people_count), (4, True, False, 0))
        self.assertEqual(OccupancyLog.objects.count(), 1)
        self.assertEqual(OccupancyLog.objects.get().free_checkouts, 0)  # closed checkouts are never "free"

        display = {h["name"]: h for h in self.client.get("/api/display/").data}
        self.assertEqual(display["H1"]["people_count"], 4)
        self.assertTrue(display["H1"]["online"])
        self.assertFalse(display["H2"]["online"])
        self.assertNotIn("polygon", display["H1"])
        self.assertFalse(display["H1"]["checkouts"][0]["is_open"])
        config = self.client.get("/api/internal/vision-config/", HTTP_X_SERVICE_TOKEN="svc").data
        self.assertIn("staff_polygon", config[0]["hallways"][0]["checkouts"][0])

    def test_state_change_is_pushed_to_display_group_once(self):
        layer = get_channel_layer()
        screen = async_to_sync(layer.new_channel)()
        async_to_sync(layer.group_add)(DISPLAY_GROUP, screen)
        cam = Camera.objects.create(name="c", ip_address="10.0.0.1", rtsp_url="rtsp://10.0.0.1/s")
        hall = Hallway.objects.create(camera=cam, name="H1", polygon=SQUARE)
        with self.captureOnCommitCallbacks(execute=True) as first:
            ingest_metrics(cam.id, {hall.id: 3}, {})
        with self.captureOnCommitCallbacks(execute=True) as second:  # identical tick
            ingest_metrics(cam.id, {hall.id: 3}, {})
        self.assertEqual((len(first), len(second)), (1, 0))
        message = async_to_sync(layer.receive)(screen)
        self.assertEqual(message["type"], "display.update")
        self.assertEqual(message["data"][0]["people_count"], 3)

    def test_vision_config_requires_token_and_rejects_bad_polygons(self):
        self.assertEqual(self.client.get("/api/internal/vision-config/").status_code, 403)
        self.assertEqual(self.client.get("/api/internal/vision-config/", HTTP_X_SERVICE_TOKEN="svc").data, [])
        csrf = self.login()
        cam = Camera.objects.create(name="c", ip_address="10.0.0.1", rtsp_url="rtsp://10.0.0.1/s")
        res = self.client.post("/api/hallways/", {"camera": cam.id, "name": "H", "polygon": [[0, 0], [2, 2]]},
                               format="json", **csrf)
        self.assertEqual(res.status_code, 400)

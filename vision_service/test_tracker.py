import cv2
import numpy as np

from model_loader import new_tracker
from tracker import blur, embed_people, face_box, zone_metrics

HALLWAYS = [{
    "id": 1, "name": "H", "polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
    "checkouts": [{"id": 10, "name": "C", "polygon": [[0, 0.8], [0.5, 0.8], [0.5, 1], [0, 1]]},
                  {"id": 11, "name": "D", "polygon": [[0, 0], [0.5, 0], [0.5, 0.2], [0, 0.2]]}],
}]


def test_zone_metrics_counts_feet_in_scaled_polygons():
    feet = [(50, 90), (20, 50), (150, 50)]  # checkout C, hallway only, outside (frame 200x100)
    metrics, is_staff = zone_metrics(feet, HALLWAYS, 200, 100)
    assert metrics == {"hallways": {1: 2}, "checkouts": {10: True, 11: False}, "open": {10: True, 11: True}}
    assert is_staff == [False, False, False]


def test_cashier_in_staff_zone_opens_checkout_and_is_not_a_customer():
    staffed = [{**HALLWAYS[0], "checkouts": [
        {**HALLWAYS[0]["checkouts"][0], "staff_polygon": [[0, 0.6], [0.5, 0.6], [0.5, 0.75], [0, 0.75]]},
        {**HALLWAYS[0]["checkouts"][1], "staff_polygon": [[0, 0.3], [0.5, 0.3], [0.5, 0.4], [0, 0.4]]},
    ]}]
    cashier, customer = (50, 70), (20, 50)  # cashier stands in C's staff zone, inside the hallway too
    metrics, is_staff = zone_metrics([cashier, customer], staffed, 200, 100)
    assert is_staff == [True, False]
    assert metrics["hallways"] == {1: 1}  # cashier not counted as waiting
    assert metrics["checkouts"] == {10: False, 11: False}  # staff never occupy a checkout
    assert metrics["open"] == {10: True, 11: False}  # D's staff zone is empty -> closed


def test_face_box_uses_keypoints_or_falls_back_to_head_region():
    kpts = np.zeros((17, 3))
    kpts[0:3] = [[50, 20, 0.9], [45, 18, 0.9], [55, 18, 0.9]]
    x1, y1, x2, y2 = face_box((0, 0, 100, 200), kpts)
    assert x1 < 45 and x2 > 55 and y1 < 18 and y2 > 20
    x1, y1, x2, y2 = face_box((0, 0, 100, 200), np.zeros((17, 3)))  # back turned
    assert (x1 + x2) / 2 == 50 and y1 < 20 < y2


def test_blur_clips_to_frame_and_changes_pixels():
    frame = np.random.randint(0, 255, (50, 50, 3), np.uint8)
    before = frame.copy()
    blur(frame, -20, -20, 30, 30)
    blur(frame, 49, 49, 80, 80)  # degenerate 1px region is ignored
    assert not np.array_equal(frame[:30, :30], before[:30, :30])
    assert np.array_equal(frame[40:, 40:], before[40:, 40:])


def test_batched_embeddings_match_deepsort_embedder():
    rng = np.random.default_rng(0)
    frame = cv2.GaussianBlur(rng.integers(0, 255, (480, 640, 3), np.uint8), (9, 9), 0)
    boxes = np.array([[10, 20, 110, 300], [300, 50, 420, 470], [600, 400, 700, 500]], np.float32)  # last one clipped
    embedder = new_tracker().embedder
    ours = embed_people(embedder, frame, boxes)
    theirs = embedder.predict([frame[max(0, int(t)):int(b), max(0, int(l)):int(r)] for l, t, r, b in boxes])
    for a, b in zip(ours, theirs):
        cosine = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        assert cosine > 0.999, cosine
    assert embed_people(embedder, frame, np.zeros((0, 4))) == []

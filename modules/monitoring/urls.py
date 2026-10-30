from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("hallways", views.HallwayViewSet, basename="hallway")
router.register("checkouts", views.CheckoutViewSet, basename="checkout")
router.register("occupancy-logs", views.OccupancyLogViewSet, basename="occupancy-log")

urlpatterns = router.urls + [
    path("display/", views.DisplayView.as_view()),
    path("internal/vision-config/", views.VisionConfigView.as_view()),
    path("internal/ingest/", views.IngestView.as_view()),
]

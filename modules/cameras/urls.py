from rest_framework.routers import SimpleRouter

from .views import CameraViewSet

router = SimpleRouter()
router.register("cameras", CameraViewSet)
urlpatterns = router.urls

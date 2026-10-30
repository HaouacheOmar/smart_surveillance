from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/health/", lambda request: JsonResponse({"status": "ok"})),
    path("api/auth/", include("modules.authentication.urls")),
    path("api/", include("modules.cameras.urls")),
    path("api/", include("modules.monitoring.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")),
]

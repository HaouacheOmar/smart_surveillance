import httpx
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from modules.ai_bridge.services import fetch_snapshot

from .models import Camera
from .serializers import CameraSerializer


class CameraViewSet(viewsets.ModelViewSet):
    queryset = Camera.objects.all()
    serializer_class = CameraSerializer

    @extend_schema(responses={(200, "image/jpeg"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def snapshot(self, request, pk=None):
        """Face-blurred JPEG frame used to map hallways and checkouts."""
        try:
            return HttpResponse(fetch_snapshot(self.get_object()), content_type="image/jpeg")
        except httpx.HTTPError as exc:
            return Response({"detail": f"Vision service error: {exc}"}, status=502)

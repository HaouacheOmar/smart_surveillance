from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.generics import ListAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.authentication.services import HasServiceToken
from modules.cameras.models import Camera

from .models import Checkout, Hallway, OccupancyLog
from .serializers import (
    CheckoutSerializer, DisplaySerializer, HallwaySerializer, IngestSerializer, OccupancyLogSerializer,
)
from .services import ingest_metrics


def _filter(queryset, request, field):
    value = request.query_params.get(field)
    return queryset.filter(**{f"{field}_id": value}) if value and value.isdigit() else queryset


@extend_schema(parameters=[OpenApiParameter("camera", int)])
class HallwayViewSet(viewsets.ModelViewSet):
    serializer_class = HallwaySerializer

    def get_queryset(self):
        return _filter(Hallway.objects.prefetch_related("checkouts"), self.request, "camera")


@extend_schema(parameters=[OpenApiParameter("hallway", int)])
class CheckoutViewSet(viewsets.ModelViewSet):
    serializer_class = CheckoutSerializer

    def get_queryset(self):
        return _filter(Checkout.objects.all(), self.request, "hallway")


class LogPagination(CursorPagination):
    ordering = "-created_at"
    page_size = 100


@extend_schema(parameters=[OpenApiParameter("hallway", int)])
class OccupancyLogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = OccupancyLogSerializer
    pagination_class = LogPagination

    def get_queryset(self):
        return _filter(OccupancyLog.objects.all(), self.request, "hallway")


class DisplayView(ListAPIView):
    """Public, read-only feed for the LCD screens."""

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = DisplaySerializer
    queryset = Hallway.objects.select_related("camera").prefetch_related("checkouts")


class ServiceView(APIView):
    authentication_classes = []
    permission_classes = [HasServiceToken]


class VisionConfigView(ServiceView):
    """Active cameras with decrypted RTSP URLs and their zones (vision service only)."""

    @extend_schema(responses={200: dict})
    def get(self, request):
        cameras = Camera.objects.filter(is_active=True).prefetch_related("hallways__checkouts")
        return Response([
            {
                "id": cam.id,
                "rtsp_url": cam.authenticated_rtsp_url,
                "hallways": [
                    {
                        "id": h.id, "name": h.name, "polygon": h.polygon,
                        "checkouts": [
                            {"id": c.id, "name": c.name, "polygon": c.polygon, "staff_polygon": c.staff_polygon}
                            for c in h.checkouts.all()
                        ],
                    }
                    for h in cam.hallways.all()
                ],
            }
            for cam in cameras
        ])


class IngestView(ServiceView):
    @extend_schema(request=IngestSerializer, responses={204: None})
    def post(self, request):
        serializer = IngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        ingest_metrics(data["camera_id"], data["hallways"], data["checkouts"], data["open"])
        return Response(status=204)

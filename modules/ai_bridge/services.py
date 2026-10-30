"""Client for the FastAPI vision service. The service pulls its config and pushes metrics itself,
so the only call Django initiates is the mapping snapshot."""
import httpx
from django.conf import settings


def fetch_snapshot(camera) -> bytes:
    response = httpx.post(
        f"{settings.VISION_SERVICE_URL}/snapshot",
        json={"rtsp_url": camera.authenticated_rtsp_url},
        headers={"X-Service-Token": settings.SERVICE_TOKEN},
        timeout=20,
    )
    response.raise_for_status()
    return response.content

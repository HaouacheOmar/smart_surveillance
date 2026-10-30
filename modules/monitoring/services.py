from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from modules.cameras.models import Camera

from .models import Checkout, Hallway, OccupancyLog
from .serializers import DisplaySerializer

DISPLAY_GROUP = "display"


def display_payload():
    hallways = Hallway.objects.select_related("camera").prefetch_related("checkouts")
    return DisplaySerializer(hallways, many=True).data


def broadcast_display():
    """Serialise once, fan out to every connected screen through the channel layer."""
    async_to_sync(get_channel_layer().group_send)(DISPLAY_GROUP, {"type": "display.update", "data": display_payload()})


@transaction.atomic
def ingest_metrics(camera_id, hallway_counts, checkout_states, open_states=None):
    """Apply one metrics tick from the vision service. Only zones of `camera_id` are touched,
    and only changed rows are written."""
    now = timezone.now()
    Camera.objects.filter(pk=camera_id).update(last_seen_at=now)

    hallways = list(Hallway.objects.filter(camera_id=camera_id).prefetch_related("checkouts"))
    changed_hallways, changed_checkouts, logs = [], [], []
    for hallway in hallways:
        dirty = False
        count = hallway_counts.get(hallway.id)
        if count is not None and count != hallway.people_count:
            hallway.people_count, hallway.updated_at, dirty = count, now, True
            changed_hallways.append(hallway)
        for checkout in hallway.checkouts.all():
            occupied = checkout_states.get(checkout.id, checkout.is_occupied)
            is_open = (open_states or {}).get(checkout.id, checkout.is_open)
            if (occupied, is_open) != (checkout.is_occupied, checkout.is_open):
                checkout.is_occupied, checkout.is_open, checkout.updated_at, dirty = occupied, is_open, now, True
                changed_checkouts.append(checkout)
        if dirty:
            free = sum(c.is_open and not c.is_occupied for c in hallway.checkouts.all())
            logs.append(OccupancyLog(hallway=hallway, people_count=hallway.people_count, free_checkouts=free))

    Hallway.objects.bulk_update(changed_hallways, ["people_count", "updated_at"])
    Checkout.objects.bulk_update(changed_checkouts, ["is_occupied", "is_open", "updated_at"])
    OccupancyLog.objects.bulk_create(logs)
    if logs:
        transaction.on_commit(broadcast_display)

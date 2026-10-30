from django.core.exceptions import ValidationError
from django.db import models

from modules.cameras.models import Camera


def validate_polygon(value):
    """Polygon = list of >= 3 [x, y] points normalised to 0..1 (resolution independent)."""
    ok = (
        isinstance(value, list) and len(value) >= 3
        and all(
            isinstance(p, list) and len(p) == 2
            and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in p)
            for p in value
        )
    )
    if not ok:
        raise ValidationError("Polygon must be a list of at least 3 [x, y] points between 0 and 1.")


class Hallway(models.Model):
    camera = models.ForeignKey(Camera, on_delete=models.CASCADE, related_name="hallways")
    name = models.CharField(max_length=100)
    polygon = models.JSONField(validators=[validate_polygon])
    people_count = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Checkout(models.Model):
    hallway = models.ForeignKey(Hallway, on_delete=models.CASCADE, related_name="checkouts")
    name = models.CharField(max_length=100)
    polygon = models.JSONField(validators=[validate_polygon], help_text="Customer side of the counter")
    # Where the cashier stands. People inside it are staff: never counted as waiting, never "occupy" a checkout.
    staff_polygon = models.JSONField(null=True, blank=True, validators=[validate_polygon])
    is_occupied = models.BooleanField(default=False, editable=False)
    # Staffed right now. Always True when no staff_polygon is mapped (state unknown, assume open).
    is_open = models.BooleanField(default=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OccupancyLog(models.Model):
    """Append-only history, written only when a hallway's state changes."""

    hallway = models.ForeignKey(Hallway, on_delete=models.CASCADE, related_name="logs")
    people_count = models.PositiveIntegerField()
    free_checkouts = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["hallway", "-created_at"])]

from rest_framework import serializers

from .models import Checkout, Hallway, OccupancyLog


class CheckoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Checkout
        fields = ["id", "hallway", "name", "polygon", "staff_polygon", "is_occupied", "is_open", "updated_at"]


class HallwaySerializer(serializers.ModelSerializer):
    checkouts = CheckoutSerializer(many=True, read_only=True)

    class Meta:
        model = Hallway
        fields = ["id", "camera", "name", "polygon", "people_count", "updated_at", "checkouts"]


class OccupancyLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OccupancyLog
        fields = ["id", "hallway", "people_count", "free_checkouts", "created_at"]


class DisplayCheckoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Checkout
        fields = ["id", "name", "is_occupied", "is_open"]


class DisplaySerializer(serializers.ModelSerializer):
    """Public LCD payload: no polygons, no camera details."""

    checkouts = DisplayCheckoutSerializer(many=True, read_only=True)
    online = serializers.BooleanField(source="camera.is_online", read_only=True)

    class Meta:
        model = Hallway
        fields = ["id", "name", "people_count", "online", "checkouts"]


class IngestSerializer(serializers.Serializer):
    camera_id = serializers.IntegerField()
    hallways = serializers.DictField(child=serializers.IntegerField(min_value=0))
    checkouts = serializers.DictField(child=serializers.BooleanField())
    open = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)

    def _int_keys(self, value):
        try:
            return {int(k): v for k, v in value.items()}
        except ValueError:
            raise serializers.ValidationError("Keys must be integer ids.")

    validate_hallways = validate_checkouts = validate_open = _int_keys

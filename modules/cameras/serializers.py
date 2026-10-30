from urllib.parse import urlsplit

from rest_framework import serializers

from .models import Camera


class CameraSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, style={"input_type": "password"})
    online = serializers.BooleanField(source="is_online", read_only=True)

    class Meta:
        model = Camera
        fields = [
            "id", "name", "ip_address", "rtsp_url", "username", "password",
            "is_active", "online", "last_seen_at", "created_at", "updated_at",
        ]

    def validate_rtsp_url(self, value):
        parts = urlsplit(value)
        if parts.scheme not in ("rtsp", "rtsps") or not parts.hostname:
            raise serializers.ValidationError("Must be an rtsp:// or rtsps:// URL.")
        if parts.username or parts.password:
            raise serializers.ValidationError("Put credentials in the username/password fields, not the URL.")
        return value

    def _save(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    def create(self, validated_data):
        return self._save(Camera(), validated_data)

    def update(self, instance, validated_data):
        return self._save(instance, validated_data)

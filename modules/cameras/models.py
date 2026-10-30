import base64
import hashlib
from datetime import timedelta
from urllib.parse import quote, urlsplit, urlunsplit

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models
from django.utils import timezone


def _fernet():
    key = hashlib.sha256(settings.FIELD_ENCRYPTION_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class Camera(models.Model):
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    rtsp_url = models.CharField(max_length=500, help_text="RTSP URL without credentials")
    username = models.CharField(max_length=100, blank=True)
    password_encrypted = models.TextField(blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def set_password(self, raw):
        self.password_encrypted = _fernet().encrypt(raw.encode()).decode() if raw else ""

    def get_password(self):
        return _fernet().decrypt(self.password_encrypted.encode()).decode() if self.password_encrypted else ""

    @property
    def authenticated_rtsp_url(self):
        """RTSP URL with decrypted credentials. Only ever sent to the vision service."""
        parts = urlsplit(self.rtsp_url)
        if not self.username:
            return self.rtsp_url
        host = parts.hostname + (f":{parts.port}" if parts.port else "")
        creds = quote(self.username, safe="") + ":" + quote(self.get_password(), safe="")
        return urlunsplit(parts._replace(netloc=f"{creds}@{host}"))

    @property
    def is_online(self):
        cutoff = timezone.now() - timedelta(seconds=settings.CAMERA_OFFLINE_AFTER_SECONDS)
        return bool(self.last_seen_at and self.last_seen_at >= cutoff)

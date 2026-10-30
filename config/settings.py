import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = os.environ.get

DEBUG = env("DJANGO_DEBUG", "0") == "1"


def secret(name):
    """Required in production; a throwaway value is allowed only with DEBUG."""
    value = env(name)
    if not value and not DEBUG:
        raise ImproperlyConfigured(f"{name} must be set")
    return value or f"dev-{name.lower()}"


SECRET_KEY = secret("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "modules.authentication",
    "modules.cameras",
    "modules.monitoring",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}]  # Swagger UI page

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Redis fans WebSocket pushes out across workers/hosts and backs the shared throttle cache.
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    # socket_timeout must exceed channels_redis' 5 s blocking read (redis-py >= 6 defaults it to 5 s too).
    CHANNEL_LAYERS = {"default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [{"address": REDIS_URL, "socket_timeout": 10}]},
    }}
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}  # single process only
AUTH_USER_MODEL = "authentication.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = env("TIME_ZONE", "UTC")
LANGUAGE_CODE = "en-us"

if env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "NAME": env("POSTGRES_DB", "surveillance"),
            "USER": env("POSTGRES_USER", "surveillance"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["modules.authentication.services.CookieJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["modules.authentication.services.IsAdminOrReadOnly"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=24),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# JWTs live only in HttpOnly cookies; CSRF double-submit protects unsafe methods.
AUTH_COOKIE_ACCESS = "access_token"
AUTH_COOKIE_REFRESH = "refresh_token"
AUTH_COOKIE_SECURE = env("AUTH_COOKIE_SECURE", "1") == "1"
AUTH_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = AUTH_COOKIE_SECURE
CSRF_COOKIE_SAMESITE = "Strict"

SPECTACULAR_SETTINGS = {
    "TITLE": "Smart Surveillance API",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
}

# Camera passwords are Fernet-encrypted with a key derived from this secret.
FIELD_ENCRYPTION_KEY = secret("FIELD_ENCRYPTION_KEY")
# Shared secret between Django and the vision service.
SERVICE_TOKEN = secret("SERVICE_TOKEN")
VISION_SERVICE_URL = env("VISION_SERVICE_URL", "http://localhost:8001")
CAMERA_OFFLINE_AFTER_SECONDS = 15

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}

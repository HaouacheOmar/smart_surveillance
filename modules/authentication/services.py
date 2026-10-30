import hmac

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication


def set_auth_cookies(response, access, refresh=None):
    common = {"httponly": True, "secure": settings.AUTH_COOKIE_SECURE, "samesite": settings.AUTH_COOKIE_SAMESITE}
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS, access,
        max_age=int(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds()), path="/", **common,
    )
    if refresh:
        # Refresh token is only ever sent to the auth endpoints.
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH, refresh,
            max_age=int(jwt["REFRESH_TOKEN_LIFETIME"].total_seconds()), path="/api/auth/", **common,
        )


def clear_auth_cookies(response):
    response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path="/")
    response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path="/api/auth/")


class CookieJWTAuthentication(JWTAuthentication):
    """Reads the access token from the HttpOnly cookie and enforces CSRF like SessionAuthentication."""

    def authenticate(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw:
            return None
        token = self.get_validated_token(raw)
        check = CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise PermissionDenied(f"CSRF Failed: {reason}")
        return self.get_user(token), token


class IsAdminOrReadOnly(BasePermission):
    """Any authenticated user can read; writes require the admin role."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (request.method in SAFE_METHODS or user.is_admin))


class HasServiceToken(BasePermission):
    """Machine-to-machine auth for the vision service."""

    def has_permission(self, request, view):
        return hmac.compare_digest(request.headers.get("X-Service-Token", ""), settings.SERVICE_TOKEN)


class CookieJWTScheme(OpenApiAuthenticationExtension):
    target_class = "modules.authentication.services.CookieJWTAuthentication"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": settings.AUTH_COOKIE_ACCESS}

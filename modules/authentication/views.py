from django.conf import settings
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import UserSerializer
from .services import clear_auth_cookies, set_auth_cookies


class PublicAuthView(APIView):
    # No authentication: a stale access cookie must not block login/refresh/logout.
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        return 'Cookie realm="api"'  # keeps bad credentials a 401, not a 403


class LoginView(PublicAuthView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=TokenObtainPairSerializer, responses=UserSerializer)
    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = Response(UserSerializer(serializer.user).data)
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data["refresh"])
        get_token(request._request)  # issue the CSRF cookie the SPA echoes back
        return response


class RefreshView(PublicAuthView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw:
            return Response({"detail": "No refresh token."}, status=401)
        serializer = TokenRefreshSerializer(data={"refresh": raw})
        serializer.is_valid(raise_exception=True)
        response = Response(status=204)
        set_auth_cookies(response, serializer.validated_data["access"], serializer.validated_data.get("refresh"))
        return response


class LogoutView(PublicAuthView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        try:
            RefreshToken(request.COOKIES.get(settings.AUTH_COOKIE_REFRESH, "")).blacklist()
        except TokenError:
            pass
        response = Response(status=204)
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        get_token(request._request)
        return Response(UserSerializer(request.user).data)

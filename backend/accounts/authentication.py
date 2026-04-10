from __future__ import annotations

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """Read the JWT access token from an httpOnly cookie instead of the Authorization header."""

    def authenticate(self, request):
        cookie_name: str = settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token")
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token is None:
            # Fall back to header-based auth
            return super().authenticate(request)

        try:
            validated_token = self.get_validated_token(raw_token)
        except (InvalidToken, TokenError):
            # Cookie token is expired/invalid — let DRF return 401 so the
            # frontend can attempt a refresh instead of silently failing.
            raise InvalidToken("Access token expired or invalid.")

        return self.get_user(validated_token), validated_token

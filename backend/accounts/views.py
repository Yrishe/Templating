from __future__ import annotations

from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Account, User
from .permissions import IsAccountOwner, IsSubscriber
from .serializers import AccountSerializer, UserLoginSerializer, UserProfileSerializer, UserRegistrationSerializer


def _set_auth_cookies(response: Response, refresh: RefreshToken) -> None:
    jwt_settings = settings.SIMPLE_JWT
    access_cookie = jwt_settings.get("AUTH_COOKIE", "access_token")
    refresh_cookie = jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token")
    secure = jwt_settings.get("AUTH_COOKIE_SECURE", True)
    http_only = jwt_settings.get("AUTH_COOKIE_HTTP_ONLY", True)
    samesite = jwt_settings.get("AUTH_COOKIE_SAMESITE", "Lax")
    path = jwt_settings.get("AUTH_COOKIE_PATH", "/")

    access_lifetime = jwt_settings["ACCESS_TOKEN_LIFETIME"].total_seconds()
    refresh_lifetime = jwt_settings["REFRESH_TOKEN_LIFETIME"].total_seconds()

    response.set_cookie(
        access_cookie,
        str(refresh.access_token),
        max_age=int(access_lifetime),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
        path=path,
    )
    response.set_cookie(
        refresh_cookie,
        str(refresh),
        max_age=int(refresh_lifetime),
        secure=secure,
        httponly=http_only,
        samesite=samesite,
        path=path,
    )


def _clear_auth_cookies(response: Response) -> None:
    jwt_settings = settings.SIMPLE_JWT
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE", "access_token"))
    response.delete_cookie(jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token"))


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)
        _set_auth_cookies(response, refresh)
        return response


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response(UserProfileSerializer(user).data, status=status.HTTP_200_OK)
        _set_auth_cookies(response, refresh)
        return response


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        jwt_settings = settings.SIMPLE_JWT
        refresh_cookie = jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_refresh = request.COOKIES.get(refresh_cookie)
        if raw_refresh:
            try:
                token = RefreshToken(raw_refresh)
                token.blacklist()
            except (TokenError, InvalidToken):
                pass
        response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        _clear_auth_cookies(response)
        return response


class TokenRefreshCookieView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        jwt_settings = settings.SIMPLE_JWT
        refresh_cookie = jwt_settings.get("AUTH_COOKIE_REFRESH", "refresh_token")
        raw_refresh = request.COOKIES.get(refresh_cookie)
        if not raw_refresh:
            return Response({"detail": "Refresh token not found."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            refresh = RefreshToken(raw_refresh)
            response = Response({"detail": "Token refreshed."}, status=status.HTTP_200_OK)
            _set_auth_cookies(response, refresh)
            return response
        except (TokenError, InvalidToken) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


class AccountListCreateView(generics.ListCreateAPIView):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsSubscriber]

    def get_queryset(self):
        return Account.objects.filter(subscriber=self.request.user).select_related("subscriber")


class AccountDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsAccountOwner]

    def get_queryset(self):
        return Account.objects.filter(subscriber=self.request.user).select_related("subscriber")

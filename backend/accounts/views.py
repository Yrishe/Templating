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


class UserSearchView(generics.ListAPIView):
    """Search for registered users by name or email.

    Used by the project-creation flow to invite existing accounts. Returns
    only active users; excludes the requesting user. Pass ?q=... to filter.
    """

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q

        q = (self.request.query_params.get("q") or "").strip()
        role = (self.request.query_params.get("role") or "").strip()
        qs = User.objects.filter(is_active=True).exclude(pk=self.request.user.pk)
        if role:
            qs = qs.filter(role=role)
        if q:
            qs = qs.filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        return qs.order_by("email")[:20]


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


# ─── Manager-approves-Manager workflow ─────────────────────────────────────
# Replaces the previous admin-only approval gate. New manager signups land in
# `is_active=False` (set by UserRegistrationSerializer.create) and must be
# approved by an existing active manager via the endpoints below.

class _IsActiveManager(permissions.BasePermission):
    """Permission: only logged-in, *active* managers may approve other managers."""

    def has_permission(self, request: Request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and u.role == User.MANAGER and u.is_active)


class PendingManagerListView(generics.ListAPIView):
    """List all manager signups awaiting approval (active managers only)."""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, _IsActiveManager]
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(role=User.MANAGER, is_active=False).order_by("date_joined")


class PendingManagerApproveView(APIView):
    """Activate a pending manager account."""

    permission_classes = [permissions.IsAuthenticated, _IsActiveManager]

    def post(self, request: Request, pk) -> Response:
        try:
            target = User.objects.get(pk=pk, role=User.MANAGER, is_active=False)
        except User.DoesNotExist:
            return Response({"detail": "Pending manager not found."}, status=status.HTTP_404_NOT_FOUND)
        target.is_active = True
        target.save(update_fields=["is_active"])
        return Response(UserProfileSerializer(target).data, status=status.HTTP_200_OK)


class PendingManagerRejectView(APIView):
    """Reject (delete) a pending manager account."""

    permission_classes = [permissions.IsAuthenticated, _IsActiveManager]

    def post(self, request: Request, pk) -> Response:
        try:
            target = User.objects.get(pk=pk, role=User.MANAGER, is_active=False)
        except User.DoesNotExist:
            return Response({"detail": "Pending manager not found."}, status=status.HTTP_404_NOT_FOUND)
        target.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

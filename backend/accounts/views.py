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


def _auth_payload(user: User, refresh: RefreshToken) -> dict:
    """Response body for login / signup / refresh.

    The refresh token is no longer in the body — it rides in an HttpOnly
    cookie set by `_set_refresh_cookie` on the response. Only the access
    token (short-lived, in-memory on the client) comes back in JSON.
    """
    return {
        "user": UserProfileSerializer(user).data,
        "access": str(refresh.access_token),
    }


def _set_refresh_cookie(response: Response, refresh_str: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_str,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]
    # Brute-force protection: at most 10 signup attempts per minute from
    # the same client. Rate defined in settings DEFAULT_THROTTLE_RATES['auth'].
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response(_auth_payload(user, refresh), status=status.HTTP_201_CREATED)
        _set_refresh_cookie(response, str(refresh))
        return response


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    # Password-guessing protection — same 10/minute throttle as signup.
    throttle_scope = "auth"

    def post(self, request: Request) -> Response:
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response(_auth_payload(user, refresh), status=status.HTTP_200_OK)
        _set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    # AllowAny so an expired client can still trigger a clean logout — we
    # read the refresh token from the HttpOnly cookie (the browser sends
    # it on same-site POSTs), blacklist if present, and clear the cookie.
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except (TokenError, InvalidToken):
                pass
        response = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        _clear_refresh_cookie(response)
        return response


class TokenRefreshCookieView(APIView):
    """POST /api/auth/token/refresh/ — rotate tokens via HttpOnly cookie.

    Reads the refresh token from `settings.REFRESH_COOKIE_NAME`. There is
    no body fallback — legacy clients sending `{refresh: ...}` in the
    body get a 401 (finding #5). Returns `{access}` and sets the rotated
    refresh cookie on the response.
    """

    permission_classes = [permissions.AllowAny]
    # Refresh happens on every 15-minute access expiry so the rate is
    # looser than login — 30/minute.
    throttle_scope = "auth_refresh"

    def post(self, request: Request) -> Response:
        raw_refresh = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
        if not raw_refresh:
            return Response(
                {"detail": "Refresh token not found."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            refresh = RefreshToken(raw_refresh)
        except (TokenError, InvalidToken) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
        # Rotation is configured via SIMPLE_JWT['ROTATE_REFRESH_TOKENS'] +
        # BLACKLIST_AFTER_ROTATION — accessing `access_token` on the
        # existing refresh returns the newly-signed access token, and
        # str(refresh) gives back the same (now-blacklisted-next-use) refresh.
        response = Response(
            {"access": str(refresh.access_token)},
            status=status.HTTP_200_OK,
        )
        _set_refresh_cookie(response, str(refresh))
        return response


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

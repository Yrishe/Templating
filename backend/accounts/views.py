from __future__ import annotations

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

    Tokens are returned in the body so the frontend can put them in
    sessionStorage (per-tab storage) and send them via the Authorization
    header. That's what makes "two users in two tabs of the same browser"
    work — httpOnly cookies are per-origin, not per-tab, so they can't
    hold two sessions simultaneously. See PLANS.md #5 for the XSS
    mitigation plan (short access lifetime + rotation + CSP hardening).
    """
    return {
        "user": UserProfileSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(_auth_payload(user, refresh), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(_auth_payload(user, refresh), status=status.HTTP_200_OK)


class LogoutView(APIView):
    # AllowAny so a 401'd client can still blacklist its refresh token
    # without needing to re-auth first — they send `{refresh: "..."}` in
    # the body and we mark it invalid.
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        raw_refresh = request.data.get("refresh") if isinstance(request.data, dict) else None
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except (TokenError, InvalidToken):
                pass
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


class TokenRefreshCookieView(APIView):
    """POST /api/auth/token/refresh/ — rotate tokens.

    Historically this read the refresh token from an httpOnly cookie.
    Since we moved to per-tab sessionStorage for multi-user-in-one-browser
    support, the refresh token now comes in the request body instead.
    The URL name is kept for backward compatibility.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        raw_refresh = request.data.get("refresh") if isinstance(request.data, dict) else None
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
        # returning `str(refresh)` gives back the same refresh. The
        # blacklist rotation happens automatically when the client
        # eventually uses the next refresh.
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


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

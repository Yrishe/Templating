from __future__ import annotations

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


class IsManager(BasePermission):
    """Allow access only to users with the MANAGER role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.MANAGER
        )


class IsAccount(BasePermission):
    """Allow access only to users with the ACCOUNT role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.ACCOUNT
        )


IsSubscriber = IsAccount  # backward-compat alias


class IsInvitedAccount(BasePermission):
    """Allow access only to users with the INVITED_ACCOUNT role."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.INVITED_ACCOUNT
        )


class IsManagerOrReadOnly(BasePermission):
    """Allow managers full access; others read-only."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return request.user.role == request.user.MANAGER


class IsProjectMember(BasePermission):
    """Allow access only to users who are members of the project."""

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        from projects.models import ProjectMembership

        project = getattr(obj, "project", obj)
        return ProjectMembership.objects.filter(project=project, user=request.user).exists()


class IsAccountOwner(BasePermission):
    """Allow access only if the requesting user is the account's subscriber."""

    def has_object_permission(self, request: Request, view: APIView, obj) -> bool:
        # obj may be an Account or have an .account attribute
        account = getattr(obj, "account", obj)
        return account.subscriber == request.user

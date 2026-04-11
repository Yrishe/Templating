from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsManager

from .models import Notification, OutboundEmail
from .serializers import NotificationSerializer, OutboundEmailSerializer


def _visible_projects_qs(user):
    """Project pks the given user is allowed to see.

    Managers have oversight on every project; accounts/invited accounts
    only see projects they're a `ProjectMembership` row for.
    """
    from projects.models import Project, ProjectMembership
    if user.role == user.MANAGER:
        return Project.objects.values_list("pk", flat=True)
    return ProjectMembership.objects.filter(user=user).values_list(
        "project_id", flat=True
    )


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q
        user = self.request.user
        visible_project_ids = _visible_projects_qs(user)
        # Exclude notifications this user has already dismissed (per-user
        # read_by) and notifications they themselves generated (actor ==
        # user). The second rule prevents the app from nagging a user with
        # their own actions: if an account raises a change request, the
        # ensuing "contract_request" card lands on everyone else's feed
        # but not the raiser's.
        #
        # `.exclude(actor=user)` on a nullable FK is the Django footgun
        # that drops every row with `actor IS NULL` — the generated SQL
        # is `NOT (actor_id = ...)` which returns NULL for NULL rows,
        # and Postgres treats NULL in WHERE as FALSE. That would hide
        # new_email and deadline_upcoming notifications (whose actor is
        # intentionally null) from every feed. Use a Q object to keep
        # NULL actors explicitly.
        qs = (
            Notification.objects.filter(project__in=visible_project_ids)
            .exclude(read_by=user)
            .filter(Q(actor__isnull=True) | ~Q(actor=user))
            .select_related(
                "project",
                "actor",
                "triggered_by_contract_request",
                "triggered_by_timeline_event",
                "triggered_by_manager",
            )
        )
        # Allow per-project filtering so the project overview's notification
        # feed only shows notifications for that project.
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        visible_project_ids = _visible_projects_qs(request.user)
        try:
            notification = Notification.objects.get(pk=pk, project__in=visible_project_ids)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # Per-user dismissal: add the caller to `read_by`. The row stays
        # visible to everyone else who hasn't dismissed it yet. .add() is
        # idempotent so calling this twice is a no-op.
        notification.read_by.add(request.user)
        return Response(
            NotificationSerializer(notification, context={"request": request}).data
        )


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request) -> Response:
        visible_project_ids = _visible_projects_qs(request.user)
        # Dismiss every notification still visible to this user across the
        # projects they can see. Bulk through the M2M manager so we don't
        # issue N individual INSERTs.
        visible = Notification.objects.filter(
            project__in=visible_project_ids
        ).exclude(read_by=request.user)
        request.user.dismissed_notifications.add(*visible)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OutboundEmailListView(generics.ListAPIView):
    serializer_class = OutboundEmailSerializer
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def get_queryset(self):
        return OutboundEmail.objects.all().select_related("notification")

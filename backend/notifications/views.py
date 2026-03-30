from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsManager

from .models import Notification, OutboundEmail
from .serializers import NotificationSerializer, OutboundEmailSerializer


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        return Notification.objects.filter(project__in=member_project_ids).select_related(
            "project", "triggered_by_contract_request", "triggered_by_manager"
        )


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk) -> Response:
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(user=request.user).values_list("project_id", flat=True)
        try:
            notification = Notification.objects.get(pk=pk, project__in=member_project_ids)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)


class OutboundEmailListView(generics.ListAPIView):
    serializer_class = OutboundEmailSerializer
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def get_queryset(self):
        return OutboundEmail.objects.all().select_related("notification")

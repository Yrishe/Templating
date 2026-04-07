from __future__ import annotations

from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from notifications.models import Notification
from notifications.serializers import NotificationSerializer
from projects.models import Project, ProjectMembership
from projects.serializers import ProjectSerializer

from .serializers import DashboardSerializer


class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user

        member_project_ids = list(
            ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
        )

        # Notifications scoped to user's projects
        notifications_qs = Notification.objects.filter(project__in=member_project_ids)
        unread_count = notifications_qs.filter(is_read=False).count()
        recent_notifications = NotificationSerializer(
            notifications_qs[:5], many=True
        ).data

        # Projects — split active vs completed for dashboard stat cards
        projects_qs = Project.objects.filter(id__in=member_project_ids).select_related("account")
        active_projects_count = projects_qs.filter(status=Project.ACTIVE).count()
        completed_projects_count = projects_qs.filter(status=Project.COMPLETED).count()
        recent_projects = ProjectSerializer(
            projects_qs.filter(status=Project.ACTIVE)[:5], many=True
        ).data

        payload: dict = {
            "role": user.role,
            "unread_notification_count": unread_count,  # kept for navbar bell badge
            "project_count": active_projects_count,
            "completed_projects": completed_projects_count,
            "recent_notifications": recent_notifications,
            "recent_projects": recent_projects,
            "pending_contract_requests": 0,
            "active_contracts": 0,
            "account_count": 0,
            "pending_manager_count": 0,
        }

        if user.role == User.MANAGER:
            from contracts.models import Contract, ContractRequest

            payload["pending_contract_requests"] = ContractRequest.objects.filter(
                status=ContractRequest.PENDING
            ).count()
            payload["active_contracts"] = Contract.objects.filter(
                status=Contract.ACTIVE, project__in=member_project_ids
            ).count()
            payload["pending_manager_count"] = User.objects.filter(
                role=User.MANAGER, is_active=False
            ).count()

        elif user.role == User.SUBSCRIBER:
            from accounts.models import Account

            payload["account_count"] = Account.objects.filter(subscriber=user).count()

        serializer = DashboardSerializer(data=payload)
        serializer.is_valid()  # always valid — data is server-generated
        return Response(serializer.initial_data)

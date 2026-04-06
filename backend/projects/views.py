from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAccount, IsManager, IsProjectMember

from .models import Project, ProjectMembership, Timeline, TimelineEvent
from .serializers import (
    ProjectDetailSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    TimelineEventSerializer,
    TimelineSerializer,
)


class ProjectListCreateView(generics.ListCreateAPIView):
    """List projects the current user is a member of, or create a new project."""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProjectDetailSerializer
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        base_qs = Project.objects.select_related("account").prefetch_related("memberships__user")
        # Managers see all projects as a team overview
        if user.role == user.MANAGER:
            return base_qs.all()
        return base_qs.filter(memberships__user=user).distinct()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != user.ACCOUNT:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only account users can create projects.")
        # Auto-assign (or create) the user's Account profile
        from accounts.models import Account
        account, _ = Account.objects.get_or_create(
            subscriber=user,
            defaults={"name": user.get_full_name() or user.email, "email": user.email},
        )
        project: Project = serializer.save(account=account)
        # Add creator as member and auto-provision linked resources
        ProjectMembership.objects.get_or_create(project=project, user=user)
        Timeline.objects.get_or_create(project=project)
        from chat.models import Chat
        Chat.objects.get_or_create(project=project)
        from email_organiser.models import EmailOrganiser
        EmailOrganiser.objects.get_or_create(project=project)


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProjectDetailSerializer
        return ProjectSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Project.objects.filter(memberships__user=user)
            .select_related("account")
            .prefetch_related("memberships__user")
            .distinct()
        )


class ProjectTimelineView(generics.RetrieveAPIView):
    serializer_class = TimelineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        project_id = self.kwargs["project_id"]
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")
        if not ProjectMembership.objects.filter(project=project, user=self.request.user).exists():
            raise PermissionDenied("You are not a member of this project.")
        timeline, _ = Timeline.objects.get_or_create(project=project)
        return timeline


class TimelineEventCreateView(generics.CreateAPIView):
    serializer_class = TimelineEventSerializer
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def perform_create(self, serializer):
        project_id = self.kwargs["project_id"]
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")
        if not ProjectMembership.objects.filter(project=project, user=self.request.user).exists():
            raise PermissionDenied("You are not a member of this project.")
        timeline, _ = Timeline.objects.get_or_create(project=project)
        serializer.save(timeline=timeline)


class ProjectMemberAddView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, project_id) -> Response:
        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            raise NotFound("Project not found.")

        is_manager = request.user.role == request.user.MANAGER
        is_account_owner = project.account.subscriber_id == request.user.pk
        if not (is_manager or is_account_owner):
            raise PermissionDenied("Only managers or account owners can add members.")

        serializer = ProjectMembershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAccount, IsManager, IsProjectMember

from .models import Project, ProjectMembership, Tag, Timeline, TimelineEvent
from .serializers import (
    ProjectDetailSerializer,
    ProjectMembershipSerializer,
    ProjectSerializer,
    TagSerializer,
    TimelineEventSerializer,
    TimelineSerializer,
)


# Auto-generated inbound mailbox suffix — see Phase 3 (8) design notes for the
# real domain to use once SES Inbound is wired up.
PROJECT_INBOUND_DOMAIN = "inbound.contractmgr.app"


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
        from accounts.models import Account, User as UserModel

        if user.role not in (user.ACCOUNT, user.MANAGER):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only account or manager users can create projects.")

        # A manager may target a specific owner via `owner_user_id` (any active
        # user). When omitted, the project is owned by the creator themselves.
        owner_user = user
        owner_user_id = self.request.data.get("owner_user_id")
        if owner_user_id:
            if user.role != user.MANAGER and str(owner_user_id) != str(user.pk):
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Only managers can assign projects to other users.")
            try:
                owner_user = UserModel.objects.get(pk=owner_user_id, is_active=True)
            except UserModel.DoesNotExist:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"owner_user_id": "No active user with this id."})

        account, _ = Account.objects.get_or_create(
            subscriber=owner_user,
            defaults={
                "name": owner_user.get_full_name() or owner_user.email,
                "email": owner_user.email,
            },
        )
        project: Project = serializer.save(account=account)
        # Auto-generate the inbound mailbox address — replaces manual entry on
        # the create form. Uses the first 8 chars of the UUID for a short slug.
        project.generic_email = f"proj-{str(project.id)[:8]}@{PROJECT_INBOUND_DOMAIN}"
        project.save(update_fields=["generic_email"])
        # Add creator and (if different) the owner as members.
        ProjectMembership.objects.get_or_create(project=project, user=user)
        if owner_user.pk != user.pk:
            ProjectMembership.objects.get_or_create(project=project, user=owner_user)
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


class ProjectMembershipListView(generics.ListAPIView):
    """List memberships for a project, filtered by ?project= query param."""

    serializer_class = ProjectMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = ProjectMembership.objects.select_related("user")
        # Non-managers can only see memberships for projects they belong to
        if user.role != user.MANAGER:
            my_projects = ProjectMembership.objects.filter(user=user).values_list("project_id", flat=True)
            qs = qs.filter(project__in=my_projects)
        project_id = self.request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs


class ProjectMemberAddView(APIView):
    """Invite a user to a project — only registered users can be added.

    The serializer accepts either `user_id` (uuid) or `email`. If the email
    does not match a registered User, the request is rejected with 400, so
    invitations cannot be sent to addresses without an account.
    """

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


class TagListCreateView(generics.ListCreateAPIView):
    """List all tags and let any authenticated user create new ones."""

    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Tag.objects.all()
    pagination_class = None

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class TagDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a tag — any authenticated user may delete."""

    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    permission_classes = [permissions.IsAuthenticated]

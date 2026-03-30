from __future__ import annotations

from rest_framework import generics, permissions
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import RetrieveAPIView

from projects.models import Project, ProjectMembership

from .models import Chat, Message
from .serializers import ChatSerializer, MessageSerializer


def _get_project_for_user(project_id, user) -> Project:
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise NotFound("Project not found.")
    if not ProjectMembership.objects.filter(project=project, user=user).exists():
        raise PermissionDenied("You are not a member of this project.")
    return project


class ChatDetailView(RetrieveAPIView):
    serializer_class = ChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        project = _get_project_for_user(self.kwargs["project_id"], self.request.user)
        chat, _ = Chat.objects.get_or_create(project=project)
        return chat


class MessageListView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = _get_project_for_user(self.kwargs["project_id"], self.request.user)
        try:
            chat = Chat.objects.get(project=project)
        except Chat.DoesNotExist:
            return Message.objects.none()
        return Message.objects.filter(chat=chat).select_related("author")

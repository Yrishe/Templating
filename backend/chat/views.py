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


class MessageListView(generics.ListCreateAPIView):
    """List or post chat messages over HTTP.

    The WebSocket consumer is the primary delivery channel, but we also expose
    a `POST` here so the chat keeps working when the WS connection is down
    (e.g. when the dev server is running plain `runserver` without daphne).
    """

    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        project = _get_project_for_user(self.kwargs["project_id"], self.request.user)
        chat, _ = Chat.objects.get_or_create(project=project)
        return Message.objects.filter(chat=chat).select_related("author").order_by("created_at")

    def perform_create(self, serializer):
        project = _get_project_for_user(self.kwargs["project_id"], self.request.user)
        chat, _ = Chat.objects.get_or_create(project=project)
        message = serializer.save(chat=chat, author=self.request.user)
        # Best-effort: notify other members and broadcast over the WS group if
        # one is connected. Both are safe no-ops when the underlying services
        # are unavailable.
        try:
            from notifications.tasks import create_chat_message_notification
            create_chat_message_notification.delay(str(message.id))
        except Exception:
            pass
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            layer = get_channel_layer()
            if layer is not None:
                async_to_sync(layer.group_send)(
                    f"chat_{project.pk}",
                    {
                        "type": "chat_message",
                        "message_id": str(message.id),
                        "content": message.content,
                        "author_id": str(self.request.user.id),
                        "author_email": self.request.user.email,
                        "created_at": message.created_at.isoformat(),
                    },
                )
        except Exception:
            pass

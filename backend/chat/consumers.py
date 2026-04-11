from __future__ import annotations

import json
import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time project chat."""

    async def connect(self) -> None:
        self.project_id: str = self.scope["url_route"]["kwargs"]["project_id"]
        self.room_group_name = f"chat_{self.project_id}"

        # Auth: per-tab sessionStorage means we can't use cookies on the WS
        # upgrade. The frontend passes the access token as `?token=...` on
        # the WS URL — parse it, verify via SimpleJWT, and load the user.
        user = await self._authenticate_from_query_string()
        if user is None:
            await self.close(code=4001)
            return
        self.scope["user"] = user

        # Verify project membership
        is_member = await self._check_membership(user, self.project_id)
        if not is_member:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        logger.info("ChatConsumer: %s connected to %s", user, self.room_group_name)

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data: str = "", bytes_data: bytes = b"") -> None:
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self.send(text_data=json.dumps({"error": "Invalid JSON."}))
            return

        content = data.get("content", "").strip()
        if not content:
            await self.send(text_data=json.dumps({"error": "Empty message."}))
            return

        user = self.scope["user"]
        message = await self._save_message(user, content)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": str(message.id),
                "content": message.content,
                "author_id": str(user.id),
                "author_email": user.email,
                "created_at": message.created_at.isoformat(),
            },
        )

    async def chat_message(self, event: dict) -> None:
        """Broadcast message to WebSocket."""
        await self.send(text_data=json.dumps(event))

    # ------------------------------------------------------------------
    # Database helpers (run in thread pool)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _authenticate_from_query_string(self):
        """Parse `?token=...` from the WS URL and verify via SimpleJWT."""
        raw_query = self.scope.get("query_string", b"").decode("utf-8", errors="ignore")
        params = parse_qs(raw_query)
        tokens = params.get("token", [])
        if not tokens:
            return None
        raw_token = tokens[0]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model

            access = AccessToken(raw_token)
            User = get_user_model()
            return User.objects.get(pk=access["user_id"])
        except Exception:
            logger.info("ChatConsumer: token verification failed")
            return None

    @database_sync_to_async
    def _check_membership(self, user, project_id: str) -> bool:
        from projects.models import ProjectMembership

        # Managers have oversight on every project's chat — same rule as
        # the HTTP views and the projects list endpoint.
        if getattr(user, "role", None) == "manager":
            return True
        return ProjectMembership.objects.filter(project_id=project_id, user=user).exists()

    @database_sync_to_async
    def _save_message(self, user, content: str):
        from chat.models import Chat, Message
        from notifications.tasks import create_chat_message_notification

        chat = Chat.objects.get(project_id=self.project_id)
        message = Message.objects.create(chat=chat, author=user, content=content)
        # Fire a project-scoped notification for the new chat message
        create_chat_message_notification.delay(str(message.id))
        return message

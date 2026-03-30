from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import UserProfileSerializer

from .models import Chat, Message


class MessageSerializer(serializers.ModelSerializer):
    author = UserProfileSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "chat", "author", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "chat", "author", "created_at", "updated_at"]


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ["id", "project", "created_at"]
        read_only_fields = fields

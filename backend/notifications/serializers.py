from __future__ import annotations

from rest_framework import serializers

from .models import Notification, OutboundEmail


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "project", "type", "triggered_by_contract_request",
            "triggered_by_manager", "is_read", "created_at",
        ]
        read_only_fields = fields


class OutboundEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundEmail
        fields = [
            "id", "notification", "to_address", "from_address",
            "subject", "body", "status", "created_at", "sent_at",
        ]
        read_only_fields = fields

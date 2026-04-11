from __future__ import annotations

from rest_framework import serializers

from .models import Notification, OutboundEmail


class NotificationSerializer(serializers.ModelSerializer):
    # `is_read` is reported from the current user's perspective. Since the
    # list view already filters out notifications the user has dismissed,
    # this will normally return False — but a direct fetch (e.g. on click)
    # will reflect the dismissal state correctly.
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "project", "type", "actor",
            "triggered_by_contract_request",
            "triggered_by_timeline_event",
            "triggered_by_manager",
            "is_read", "created_at",
        ]
        read_only_fields = fields

    def get_is_read(self, obj: Notification) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.read_by.filter(pk=request.user.pk).exists()


class OutboundEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundEmail
        fields = [
            "id", "notification", "to_address", "from_address",
            "subject", "body", "status", "created_at", "sent_at",
        ]
        read_only_fields = fields

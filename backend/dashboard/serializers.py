from __future__ import annotations

from rest_framework import serializers


class DashboardSerializer(serializers.Serializer):
    """Aggregated dashboard payload — shape varies by role."""

    role = serializers.CharField(read_only=True)
    unread_notification_count = serializers.IntegerField(read_only=True)
    project_count = serializers.IntegerField(read_only=True)
    completed_projects = serializers.IntegerField(read_only=True, default=0)
    recent_notifications = serializers.ListField(read_only=True)
    recent_projects = serializers.ListField(read_only=True)
    # Manager-specific
    pending_contract_requests = serializers.IntegerField(read_only=True, default=0)
    active_contracts = serializers.IntegerField(read_only=True, default=0)
    pending_manager_count = serializers.IntegerField(read_only=True, default=0)
    # Subscriber-specific
    account_count = serializers.IntegerField(read_only=True, default=0)

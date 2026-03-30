from __future__ import annotations

from django.contrib import admin

from .models import Notification, OutboundEmail


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["type", "project", "is_read", "created_at"]
    list_filter = ["type", "is_read"]
    search_fields = ["project__name"]
    raw_id_fields = ["project", "triggered_by_contract_request", "triggered_by_manager"]


@admin.register(OutboundEmail)
class OutboundEmailAdmin(admin.ModelAdmin):
    list_display = ["to_address", "subject", "status", "created_at", "sent_at"]
    list_filter = ["status"]
    search_fields = ["to_address", "subject"]
    raw_id_fields = ["notification"]

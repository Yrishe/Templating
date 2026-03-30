from __future__ import annotations

from django.contrib import admin

from .models import Contract, ContractRequest


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "status", "created_by", "created_at", "activated_at"]
    list_filter = ["status"]
    search_fields = ["title", "project__name"]
    raw_id_fields = ["project", "created_by"]


@admin.register(ContractRequest)
class ContractRequestAdmin(admin.ModelAdmin):
    list_display = ["account", "project", "status", "created_at", "reviewed_at", "reviewed_by"]
    list_filter = ["status"]
    search_fields = ["account__name", "project__name"]
    raw_id_fields = ["account", "project", "reviewed_by"]

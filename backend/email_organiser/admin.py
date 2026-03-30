from __future__ import annotations

from django.contrib import admin

from .models import EmailOrganiser, FinalResponse, InvitedAccount, Recipient


@admin.register(InvitedAccount)
class InvitedAccountAdmin(admin.ModelAdmin):
    list_display = ["user", "project", "invited_at", "invited_by"]
    raw_id_fields = ["project", "user", "invited_by"]


@admin.register(EmailOrganiser)
class EmailOrganiserAdmin(admin.ModelAdmin):
    list_display = ["project", "created_at", "updated_at"]
    raw_id_fields = ["project"]


@admin.register(FinalResponse)
class FinalResponseAdmin(admin.ModelAdmin):
    list_display = ["subject", "email_organiser", "status", "created_at", "sent_at"]
    list_filter = ["status"]
    raw_id_fields = ["email_organiser", "edited_by"]


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "final_response"]
    raw_id_fields = ["final_response"]

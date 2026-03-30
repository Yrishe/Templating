from __future__ import annotations

from django.contrib import admin

from .models import Chat, Message


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ["project", "created_at"]
    raw_id_fields = ["project"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["author", "chat", "created_at"]
    raw_id_fields = ["chat", "author"]
    search_fields = ["content", "author__email"]

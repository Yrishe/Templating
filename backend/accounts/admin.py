from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Account, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "role", "is_staff", "is_active"]
    list_filter = ["role", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Role & Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "is_staff", "is_active"),
            },
        ),
    )
    # username is removed from the model
    username_field = "email"


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "subscriber", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "email", "subscriber__email"]
    raw_id_fields = ["subscriber"]

from __future__ import annotations

from django.contrib import admin

from .models import Project, ProjectMembership, Timeline, TimelineEvent


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "account", "generic_email", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["name", "account__name"]
    raw_id_fields = ["account"]


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "joined_at"]
    raw_id_fields = ["project", "user"]


@admin.register(Timeline)
class TimelineAdmin(admin.ModelAdmin):
    list_display = ["project", "created_at"]
    raw_id_fields = ["project"]


@admin.register(TimelineEvent)
class TimelineEventAdmin(admin.ModelAdmin):
    list_display = ["title", "timeline", "status", "start_date", "end_date"]
    list_filter = ["status"]
    search_fields = ["title"]
    raw_id_fields = ["timeline"]

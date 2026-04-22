from __future__ import annotations

from django.contrib import admin

from .models import AISuggestionFeedback, FeatureFeedback


@admin.register(AISuggestionFeedback)
class AISuggestionFeedbackAdmin(admin.ModelAdmin):
    list_display = ["target_type", "rating", "user", "project", "model", "created_at"]
    list_filter = ["target_type", "rating", "project"]
    search_fields = ["reason", "user__email"]
    raw_id_fields = ["user", "project"]
    readonly_fields = ["id", "created_at", "updated_at", "model", "provider"]


@admin.register(FeatureFeedback)
class FeatureFeedbackAdmin(admin.ModelAdmin):
    list_display = ["feature_key", "rating", "user", "project", "created_at"]
    list_filter = ["feature_key", "rating", "project"]
    search_fields = ["comment", "user__email", "feature_key"]
    raw_id_fields = ["user", "project"]
    readonly_fields = ["id", "created_at", "updated_at", "route"]

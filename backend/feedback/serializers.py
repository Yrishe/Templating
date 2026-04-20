from __future__ import annotations

from rest_framework import serializers

from .models import AISuggestionFeedback


class AISuggestionFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISuggestionFeedback
        fields = [
            "id",
            "user",
            "project",
            "target_type",
            "target_id",
            "rating",
            "reason",
            "model",
            "provider",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "project",
            "model",
            "provider",
            "created_at",
            "updated_at",
        ]

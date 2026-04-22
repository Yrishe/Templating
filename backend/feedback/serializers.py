from __future__ import annotations

from rest_framework import serializers

from .models import AISuggestionFeedback, FeatureFeedback


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


class FeatureFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFeedback
        fields = [
            "id",
            "user",
            "feature_key",
            "rating",
            "comment",
            "project",
            "route",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "user", "created_at", "updated_at"]
        extra_kwargs = {
            # Project is genuinely optional (app-global features have no
            # project). ModelSerializer sometimes infers required=True on
            # FKs with null=True; make it explicit so the endpoint accepts
            # posts that omit the key entirely.
            "project": {"required": False, "allow_null": True},
            "comment": {"required": False, "allow_blank": True},
            "route": {"required": False, "allow_blank": True},
        }

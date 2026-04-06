from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import UserProfileSerializer

from .models import Project, ProjectMembership, Timeline, TimelineEvent


class TimelineEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimelineEvent
        fields = ["id", "title", "description", "start_date", "end_date", "status", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class TimelineSerializer(serializers.ModelSerializer):
    events = TimelineEventSerializer(many=True, read_only=True)

    class Meta:
        model = Timeline
        fields = ["id", "project", "events", "created_at", "updated_at"]
        read_only_fields = ["id", "project", "created_at", "updated_at"]


class ProjectMembershipSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user", "user_id", "joined_at"]
        read_only_fields = ["id", "project", "joined_at", "user"]

    def create(self, validated_data):
        from accounts.models import User

        user_id = validated_data.pop("user_id")
        user = User.objects.get(pk=user_id)
        validated_data["user"] = user
        return super().create(validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "account", "name", "description", "generic_email", "created_at", "updated_at"]
        read_only_fields = ["id", "account", "created_at", "updated_at"]


class ProjectDetailSerializer(ProjectSerializer):
    memberships = ProjectMembershipSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["memberships"]  # type: ignore[operator]

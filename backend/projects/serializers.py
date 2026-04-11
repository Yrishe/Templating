from __future__ import annotations

from rest_framework import serializers

from accounts.serializers import UserProfileSerializer

from .models import Project, ProjectMembership, Tag, Timeline, TimelineEvent


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color", "created_at"]
        read_only_fields = ["id", "created_at"]


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
    user_id = serializers.UUIDField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)

    class Meta:
        model = ProjectMembership
        fields = ["id", "project", "user", "user_id", "email", "joined_at"]
        read_only_fields = ["id", "project", "joined_at", "user"]

    def validate(self, attrs):
        if not attrs.get("user_id") and not attrs.get("email"):
            raise serializers.ValidationError("Either user_id or email is required.")
        return attrs

    def create(self, validated_data):
        from accounts.models import User

        user_id = validated_data.pop("user_id", None)
        email = validated_data.pop("email", None)

        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"user_id": "No registered user found with this ID."}
                )
        else:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    {"email": "No registered user found with this email address."}
                )

        validated_data["user"] = user
        return super().create(validated_data)


class ProjectSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    # Write-only field accepting a list of tag UUIDs to attach during create/update.
    tag_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        write_only=True,
        required=False,
        source="tags",
    )
    # The User who owns the project's Account. Exposed so the frontend can
    # tell when a manager is looking at a project they created and kept for
    # themselves — used to hide the Contract Requests review panel in that
    # case (managers don't raise requests on their own project).
    account_subscriber_id = serializers.UUIDField(
        source="account.subscriber_id", read_only=True
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "account",
            "account_subscriber_id",
            "name",
            "description",
            "generic_email",
            "status",
            "tags",
            "tag_ids",
            "created_at",
            "updated_at",
        ]
        # generic_email is auto-generated server-side; never user-supplied
        read_only_fields = [
            "id",
            "account",
            "account_subscriber_id",
            "generic_email",
            "created_at",
            "updated_at",
        ]


class ProjectDetailSerializer(ProjectSerializer):
    memberships = ProjectMembershipSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + ["memberships"]  # type: ignore[operator]

from __future__ import annotations

from rest_framework import serializers

from .models import EmailOrganiser, FinalResponse, InvitedAccount, Recipient


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = ["id", "name", "email", "final_response"]
        read_only_fields = ["id", "final_response"]


class FinalResponseSerializer(serializers.ModelSerializer):
    recipients = RecipientSerializer(many=True, read_only=True)

    class Meta:
        model = FinalResponse
        fields = [
            "id", "email_organiser", "edited_by", "subject", "content",
            "status", "recipients", "created_at", "updated_at", "sent_at",
        ]
        read_only_fields = ["id", "email_organiser", "status", "created_at", "updated_at", "sent_at"]


class EmailOrganiserSerializer(serializers.ModelSerializer):
    final_responses = FinalResponseSerializer(many=True, read_only=True)

    class Meta:
        model = EmailOrganiser
        fields = ["id", "project", "ai_context", "final_responses", "created_at", "updated_at"]
        read_only_fields = ["id", "project", "created_at", "updated_at"]


class InvitedAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitedAccount
        fields = ["id", "project", "user", "invited_at", "invited_by"]
        read_only_fields = ["id", "project", "invited_at", "invited_by"]

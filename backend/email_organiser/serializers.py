from __future__ import annotations

from rest_framework import serializers

from .models import EmailOrganiser, FinalResponse, IncomingEmail, InvitedAccount, Recipient


class IncomingEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomingEmail
        fields = [
            "id",
            "project",
            "sender_email",
            "sender_name",
            "subject",
            "body_plain",
            "body_html",
            "message_id",
            "received_at",
            "is_processed",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


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
            "id", "email_organiser", "edited_by", "source_incoming_email",
            "subject", "content", "status", "is_ai_generated",
            "recipients", "created_at", "updated_at", "sent_at",
        ]
        read_only_fields = [
            "id", "email_organiser", "status", "is_ai_generated",
            "source_incoming_email", "created_at", "updated_at", "sent_at",
        ]


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

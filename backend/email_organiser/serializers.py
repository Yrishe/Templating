from __future__ import annotations

from rest_framework import serializers

from .models import (
    EmailAnalysis,
    EmailOrganiser,
    FinalResponse,
    IncomingEmail,
    InvitedAccount,
    Recipient,
)


class EmailAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailAnalysis
        fields = [
            "id",
            "email",
            "agent_topic",
            "risk_level",
            "risk_summary",
            "contract_references",
            "mitigation",
            "suggested_response",
            "resolution_path",
            "timeline_impact",
            "generated_timeline_event",
            "created_at",
        ]
        read_only_fields = fields


class IncomingEmailSerializer(serializers.ModelSerializer):
    analysis = EmailAnalysisSerializer(read_only=True)

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
            "is_relevant",
            "relevance",
            "category",
            "keywords",
            "is_resolved",
            "analysis",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "is_processed",
            "is_relevant",
            "relevance",
            "category",
            "keywords",
            "created_at",
        ]


# ── Legacy serializers (kept for migration/admin backward compat) ─────

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
    class Meta:
        model = EmailOrganiser
        fields = ["id", "project", "ai_context", "created_at", "updated_at"]
        read_only_fields = ["id", "project", "created_at", "updated_at"]


class InvitedAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitedAccount
        fields = ["id", "project", "user", "invited_at", "invited_by"]
        read_only_fields = ["id", "project", "invited_at", "invited_by"]

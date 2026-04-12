from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class InvitedAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="invited_accounts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="invitations",
        limit_choices_to={"role": "invited_account"},
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_invitations",
    )

    class Meta:
        unique_together = ("project", "user")

    def __str__(self) -> str:
        return f"InvitedAccount({self.user}, {self.project})"


class EmailOrganiser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="email_organiser",
    )
    ai_context = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"EmailOrganiser({self.project})"


class IncomingEmail(models.Model):
    """An inbound email routed to a project's `generic_email` mailbox.

    Created by the SES/SendGrid/Postmark inbound webhook (see
    `email_organiser.views.InboundEmailWebhookView`). Each new IncomingEmail
    triggers the AI classification pipeline which reads the email, assesses it
    against the project's contract, and organises it by category and relevance.
    """

    # ── Relevance levels ────────────────────────────────────────────────
    RELEVANCE_HIGH = "high"
    RELEVANCE_MEDIUM = "medium"
    RELEVANCE_LOW = "low"
    RELEVANCE_NONE = "none"  # irrelevant — discarded from base knowledge

    RELEVANCE_CHOICES = [
        (RELEVANCE_HIGH, "High"),
        (RELEVANCE_MEDIUM, "Medium"),
        (RELEVANCE_LOW, "Low"),
        (RELEVANCE_NONE, "Not Relevant"),
    ]

    # ── Email categories (what topic does it concern?) ──────────────────
    CATEGORY_DELAY = "delay"
    CATEGORY_DAMAGE = "damage"
    CATEGORY_SCOPE_CHANGE = "scope_change"
    CATEGORY_COSTS = "costs"
    CATEGORY_DELIVERY = "delivery"
    CATEGORY_COMPLIANCE = "compliance"
    CATEGORY_QUALITY = "quality"
    CATEGORY_DISPUTE = "dispute"
    CATEGORY_GENERAL = "general"
    CATEGORY_IRRELEVANT = "irrelevant"

    CATEGORY_CHOICES = [
        (CATEGORY_DELAY, "Delay"),
        (CATEGORY_DAMAGE, "Damage"),
        (CATEGORY_SCOPE_CHANGE, "Change of Scope"),
        (CATEGORY_COSTS, "Costs"),
        (CATEGORY_DELIVERY, "Delivery"),
        (CATEGORY_COMPLIANCE, "Compliance"),
        (CATEGORY_QUALITY, "Quality"),
        (CATEGORY_DISPUTE, "Dispute"),
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_IRRELEVANT, "Irrelevant"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="incoming_emails",
    )
    sender_email = models.EmailField()
    sender_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=998, blank=True)
    body_plain = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    # email Message-ID header — unique to dedupe webhook deliveries
    message_id = models.CharField(max_length=998, unique=True)
    received_at = models.DateTimeField()
    # Whole webhook payload kept for forensics / future re-parsing
    raw_payload = models.JSONField(null=True, blank=True)
    # Set True once the AI pipeline has finished processing this email
    is_processed = models.BooleanField(default=False)

    # ── AI classification fields (populated by the classifier agent) ────
    is_relevant = models.BooleanField(default=True)
    relevance = models.CharField(
        max_length=10, choices=RELEVANCE_CHOICES, default=RELEVANCE_MEDIUM
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL
    )
    # Comma-separated keywords extracted by the classifier
    keywords = models.TextField(blank=True)
    # Whether the occurrence raised by this email has been resolved
    is_resolved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["received_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["relevance"]),
            models.Index(fields=["is_resolved"]),
        ]

    def __str__(self) -> str:
        return f"IncomingEmail({self.sender_email}, {self.subject[:40]})"


class EmailAnalysis(models.Model):
    """AI-generated analysis of a relevant incoming email assessed against the
    project's contract. Produced by the specialized topic agent (costs, delay,
    scope, etc.) after the classifier agent has categorised the email."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.OneToOneField(
        IncomingEmail,
        on_delete=models.CASCADE,
        related_name="analysis",
    )
    # Which specialized agent produced this analysis
    agent_topic = models.CharField(max_length=30, blank=True)
    # Risk assessment
    risk_level = models.CharField(
        max_length=10,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
        default="medium",
    )
    risk_summary = models.TextField(blank=True)
    # Contract clauses referenced
    contract_references = models.TextField(blank=True)
    # Mitigation suggestions
    mitigation = models.TextField(blank=True)
    # Suggested response approach
    suggested_response = models.TextField(blank=True)
    # Resolution path
    resolution_path = models.TextField(blank=True)
    # Impact on timeline
    timeline_impact = models.TextField(blank=True)
    # FK to the auto-generated TimelineEvent (if one was created)
    generated_timeline_event = models.ForeignKey(
        "projects.TimelineEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_email_analyses",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "email analyses"

    def __str__(self) -> str:
        return f"EmailAnalysis({self.email}, {self.agent_topic})"


# ── Legacy models kept for backward compatibility with existing migrations ──

class FinalResponse(models.Model):
    """Kept for migration history. The Email Organiser no longer sends emails;
    it receives and classifies them."""

    DRAFT = "draft"
    SENT = "sent"
    SUGGESTED = "suggested"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (SUGGESTED, "AI Suggested"),
        (SENT, "Sent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_organiser = models.ForeignKey(
        EmailOrganiser,
        on_delete=models.CASCADE,
        related_name="final_responses",
    )
    edited_by = models.ForeignKey(
        InvitedAccount,
        on_delete=models.SET_NULL,
        null=True,
        related_name="final_responses",
    )
    source_incoming_email = models.ForeignKey(
        IncomingEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suggested_replies",
    )
    subject = models.CharField(max_length=998)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    is_ai_generated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"FinalResponse({self.subject[:50]})"


class Recipient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    final_response = models.ForeignKey(
        FinalResponse,
        on_delete=models.CASCADE,
        related_name="recipients",
    )

    class Meta:
        unique_together = ("email", "final_response")

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"

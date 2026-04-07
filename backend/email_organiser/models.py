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
    triggers `email_organiser.tasks.generate_suggested_reply` which uses Claude
    to draft a contract-grounded reply stored as a draft `FinalResponse`.
    """

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
    # Set True once a suggested reply has been generated for this message
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["received_at"]),
        ]

    def __str__(self) -> str:
        return f"IncomingEmail({self.sender_email}, {self.subject[:40]})"


class FinalResponse(models.Model):
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
    # Optional link back to the inbound email this is a reply to —
    # populated when Claude generates the draft from an IncomingEmail.
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
    # True for content authored by Claude (not a human draft)
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

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


class FinalResponse(models.Model):
    DRAFT = "draft"
    SENT = "sent"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
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
    subject = models.CharField(max_length=998)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
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

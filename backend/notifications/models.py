from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    CONTRACT_REQUEST = "contract_request"
    CONTRACT_UPDATE = "contract_update"
    CHAT_MESSAGE = "chat_message"
    MANAGER_ALERT = "manager_alert"
    SYSTEM = "system"

    TYPE_CHOICES = [
        (CONTRACT_REQUEST, "Contract Request"),
        (CONTRACT_UPDATE, "Contract Update"),
        (CHAT_MESSAGE, "Chat Message"),
        (MANAGER_ALERT, "Manager Alert"),
        (SYSTEM, "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    triggered_by_contract_request = models.ForeignKey(
        "contracts.ContractRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    triggered_by_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triggered_notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Notification({self.type}, project={self.project_id})"


class OutboundEmail(models.Model):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emails",
    )
    to_address = models.EmailField()
    from_address = models.EmailField()
    subject = models.CharField(max_length=998)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["to_address"]),
        ]

    def __str__(self) -> str:
        return f"OutboundEmail(to={self.to_address}, status={self.status})"

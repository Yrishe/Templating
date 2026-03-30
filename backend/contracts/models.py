from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Contract(models.Model):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="contract",
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_contracts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["project"]),
        ]

    def __str__(self) -> str:
        return self.title


class ContractRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (REJECTED, "Rejected"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="contract_requests",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="contract_requests",
    )
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reviewed_requests",
    )

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["account"]),
            models.Index(fields=["project"]),
        ]

    def __str__(self) -> str:
        return f"ContractRequest({self.account}, {self.status})"

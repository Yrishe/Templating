from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Contract(models.Model):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
    ]

    # How the contract text was extracted — helps the UI inform users about
    # quality and offer a manual paste fallback.
    TEXT_SOURCE_NONE = "none"
    TEXT_SOURCE_PYPDF = "pypdf"
    TEXT_SOURCE_TEXTRACT = "textract"
    TEXT_SOURCE_MANUAL = "manual"

    TEXT_SOURCE_CHOICES = [
        (TEXT_SOURCE_NONE, "None"),
        (TEXT_SOURCE_PYPDF, "pypdf (digital PDF)"),
        (TEXT_SOURCE_TEXTRACT, "AWS Textract (OCR)"),
        (TEXT_SOURCE_MANUAL, "Manual (pasted by user)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="contract",
    )
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="contracts/", null=True, blank=True)
    content = models.TextField(blank=True)
    text_source = models.CharField(
        max_length=10, choices=TEXT_SOURCE_CHOICES, default=TEXT_SOURCE_NONE
    )
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
    # Optional supporting document — e.g. a redlined PDF showing the requested
    # changes. Stored alongside the request so the manager can open it while
    # deciding whether to approve or reject.
    attachment = models.FileField(
        upload_to="contract_requests/", null=True, blank=True
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    # Manager's justification when approving or rejecting. Captured via the
    # approve/reject endpoints so accounts can see *why* a request moved.
    review_comment = models.TextField(blank=True)
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

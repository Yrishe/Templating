from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class AISuggestionFeedback(models.Model):
    """User 👍/👎 on a specific AI output (classification or suggestion).

    One row per (user, target_type, target_id) — re-POSTing is an idempotent
    upsert that flips the rating or attaches a reason. `project` is inferred
    server-side from the target so the caller cannot spoof which project the
    feedback belongs to.

    `model` + `provider` are snapshotted at create time so the labelled
    evaluation dataset is still readable after `ANTHROPIC_MODEL` changes.
    """

    TARGET_CLASSIFICATION = "classification"
    TARGET_SUGGESTION = "suggestion"
    TARGET_TIMELINE_EVENT = "timeline_event"

    TARGET_CHOICES = [
        (TARGET_CLASSIFICATION, "Classification"),
        (TARGET_SUGGESTION, "Suggestion"),
        (TARGET_TIMELINE_EVENT, "Timeline Event"),
    ]

    RATING_UP = 1
    RATING_DOWN = -1

    RATING_CHOICES = [
        (RATING_UP, "Up"),
        (RATING_DOWN, "Down"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ai_feedback",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="ai_feedback",
    )
    target_type = models.CharField(max_length=32, choices=TARGET_CHOICES)
    target_id = models.UUIDField()
    rating = models.SmallIntegerField(choices=RATING_CHOICES)
    reason = models.TextField(blank=True, max_length=500)
    model = models.CharField(max_length=64)
    provider = models.CharField(max_length=32, default="anthropic")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["project", "created_at"]),
        ]
        unique_together = [("user", "target_type", "target_id")]

    def __str__(self) -> str:
        return f"AISuggestionFeedback({self.target_type}:{self.target_id}, {self.rating})"

"""Feedback models.

Two surfaces today:

- `AISuggestionFeedback` — 👍 / 👎 on a specific AI artifact (email
  classification, suggested reply). Keyed by `(target_type, target_id)`;
  the project is inferred from the target so callers can't spoof it.
- `FeatureFeedback` — 👍 / 👎 on a feature as a whole. Keyed by a
  free-form dotted `feature_key` (e.g. ``projects.overview``,
  ``dashboard.home``, ``email-organiser.analysis``). Adding a new feature
  mount point does not require a backend change — the key is opaque to
  the API and only matters for downstream aggregation.
"""
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


class FeatureFeedback(models.Model):
    """User 👍 / 👎 + optional comment on a feature as a whole.

    One row per ``(user, feature_key, project)``. Re-POSTing is an
    idempotent upsert that flips the rating or updates the comment — the
    client calls the endpoint twice when the comment changes, not once.

    ``project`` is nullable so app-global features (the dashboard, the
    profile page) can collect feedback without a synthetic project.
    Postgres treats NULLs as distinct for unique constraints, but we
    still land at most one (``user``, ``feature_key``, NULL) row per user
    because every thumbs click goes through the upsert code path which
    looks for that exact triple.
    """

    RATING_UP = 1
    RATING_DOWN = -1

    RATING_CHOICES = AISuggestionFeedback.RATING_CHOICES

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="feature_feedback",
    )
    feature_key = models.CharField(max_length=64)
    rating = models.SmallIntegerField(choices=RATING_CHOICES)
    comment = models.TextField(blank=True, max_length=1000)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="feature_feedback",
    )
    # Client-captured pathname at submit time — analytics fuel, not a
    # security surface. Trusting the client is fine because rating +
    # comment are the load-bearing fields.
    route = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["feature_key", "created_at"]),
            models.Index(fields=["project", "feature_key"]),
        ]
        unique_together = [("user", "feature_key", "project")]

    def __str__(self) -> str:
        return f"FeatureFeedback({self.feature_key}, {self.rating})"

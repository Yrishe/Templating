"""AI suggestion feedback endpoint tests (Phase 1 of the research program).

Locks in the invariants from docs/research.md §A.1:

- One vote per (user, target_type, target_id). Re-POST is an idempotent
  upsert — second POST flips rating, attaches reason, keeps one row.
- `project` is inferred from the target (IncomingEmail.project for
  classifications, EmailAnalysis.email.project for suggestions). The
  caller cannot spoof it by passing it in the body.
- Cross-project targets return 404, not 403 — we don't leak existence of
  emails / analyses the caller can't see.
- `model` + `provider` are snapshotted at create time and preserved on
  update so the labelled dataset stays readable after ANTHROPIC_MODEL
  changes.
- `timeline_event` is a declared target type but not wired this phase
  (returns 400).
"""
from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from feedback.models import AISuggestionFeedback

pytestmark = pytest.mark.django_db


ENDPOINT = "/api/feedback/ai/"


def _make_analysis(email, **overrides):
    """Create an EmailAnalysis for the given incoming email. Inlined rather
    than a conftest fixture — it's only used in this module."""
    from email_organiser.models import EmailAnalysis

    defaults = {
        "email": email,
        "agent_topic": "delay",
        "risk_level": "medium",
        "risk_summary": "Supplier flags a 2-week delay.",
        "suggested_response": "Ack the delay, ask for updated timeline.",
    }
    defaults.update(overrides)
    return EmailAnalysis.objects.create(**defaults)


# ─── Happy paths ──────────────────────────────────────────────────────────


class TestCreate:
    def test_thumbs_up_on_classification_creates_row(
        self,
        subscriber_client: APIClient,
        project,
        incoming_email_factory,
    ):
        email = incoming_email_factory()
        resp = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(email.id),
                "rating": 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["rating"] == 1
        assert body["target_type"] == "classification"
        assert body["target_id"] == str(email.id)
        assert body["project"] == str(project.id)
        # model / provider snapshotted from settings
        assert body["provider"] == "anthropic"
        assert body["model"]  # non-empty
        # DB: exactly one row
        assert AISuggestionFeedback.objects.count() == 1

    def test_thumbs_down_on_suggestion_creates_row(
        self,
        subscriber_client: APIClient,
        project,
        incoming_email_factory,
    ):
        email = incoming_email_factory()
        analysis = _make_analysis(email)
        resp = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "suggestion",
                "target_id": str(analysis.id),
                "rating": -1,
                "reason": "Tone is too formal",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["rating"] == -1
        assert body["reason"] == "Tone is too formal"
        # project was inferred through analysis.email.project
        assert body["project"] == str(project.id)


# ─── Idempotent upsert ────────────────────────────────────────────────────


class TestUpsert:
    def test_repost_flips_rating_without_duplicating(
        self,
        subscriber_client: APIClient,
        project,
        incoming_email_factory,
    ):
        email = incoming_email_factory()
        payload = {
            "target_type": "classification",
            "target_id": str(email.id),
            "rating": 1,
        }
        first = subscriber_client.post(ENDPOINT, payload, format="json")
        assert first.status_code == status.HTTP_201_CREATED

        payload["rating"] = -1
        second = subscriber_client.post(ENDPOINT, payload, format="json")
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["rating"] == -1
        # Still one row in total — this is the (user, target_type, target_id)
        # uniqueness the spec requires.
        assert AISuggestionFeedback.objects.count() == 1

    def test_reason_attached_on_update(
        self,
        subscriber_client: APIClient,
        incoming_email_factory,
    ):
        email = incoming_email_factory()
        base = {
            "target_type": "classification",
            "target_id": str(email.id),
            "rating": 1,
        }
        subscriber_client.post(ENDPOINT, base, format="json")
        resp = subscriber_client.post(
            ENDPOINT, {**base, "reason": "Spot on."}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        row = AISuggestionFeedback.objects.get()
        assert row.rating == 1
        assert row.reason == "Spot on."

    def test_update_preserves_original_model_snapshot(
        self,
        subscriber_client: APIClient,
        incoming_email_factory,
    ):
        """`model` is a create-time snapshot. If ANTHROPIC_MODEL rolls over
        between the first and second POST, the stored label must still
        reflect the model in use when the rating was *first* captured —
        otherwise the labelled dataset misattributes ratings across models.
        """
        email = incoming_email_factory()
        payload = {
            "target_type": "classification",
            "target_id": str(email.id),
            "rating": 1,
        }
        with override_settings(ANTHROPIC_MODEL="claude-old"):
            subscriber_client.post(ENDPOINT, payload, format="json")
        with override_settings(ANTHROPIC_MODEL="claude-new"):
            subscriber_client.post(ENDPOINT, {**payload, "rating": -1}, format="json")
        row = AISuggestionFeedback.objects.get()
        assert row.model == "claude-old"
        assert row.rating == -1


# ─── Auth + permission boundary ───────────────────────────────────────────


class TestPermissions:
    def test_unauthenticated_is_401(
        self, api_client: APIClient, incoming_email_factory
    ):
        email = incoming_email_factory()
        resp = api_client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(email.id),
                "rating": 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cross_project_target_returns_404(
        self,
        second_account_user,
        incoming_email_factory,
    ):
        """A user who isn't a member of a project must not be able to submit
        feedback targeting an email in that project. 404 (not 403) so the
        endpoint doesn't leak which target_ids exist cross-project."""
        email = incoming_email_factory()  # belongs to `project` — owned by subscriber
        # `second_account_user` (from conftest) isn't a member of `project`.
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        access = str(RefreshToken.for_user(second_account_user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(email.id),
                "rating": 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert AISuggestionFeedback.objects.count() == 0


# ─── Validation ───────────────────────────────────────────────────────────


class TestValidation:
    def test_unknown_target_id_returns_404(self, subscriber_client: APIClient):
        import uuid

        resp = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(uuid.uuid4()),
                "rating": 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_invalid_rating_is_400(
        self, subscriber_client: APIClient, incoming_email_factory
    ):
        email = incoming_email_factory()
        resp = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(email.id),
                "rating": 0,  # must be 1 or -1
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_timeline_event_target_is_400_this_phase(
        self, subscriber_client: APIClient
    ):
        """timeline_event is declared on the model for forward compat but the
        UI / resolver for it lands in a later phase. Keep the explicit 400
        so we notice when a client starts sending it."""
        import uuid

        resp = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "timeline_event",
                "target_id": str(uuid.uuid4()),
                "rating": 1,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ─── Throttle ─────────────────────────────────────────────────────────────


class TestThrottle:
    def test_over_limit_returns_429(
        self, subscriber_client: APIClient, incoming_email_factory, monkeypatch
    ):
        """Exceeding the `ai_feedback` scoped throttle returns 429.

        We lower the rate to 2/minute so the test stays fast — the
        production setting is 30/minute.

        DRF captures `THROTTLE_RATES` on the class at import time (it
        reads `api_settings.DEFAULT_THROTTLE_RATES` once), so mutating
        Django settings at runtime doesn't propagate. We patch the
        class attribute directly instead.
        """
        from rest_framework.throttling import ScopedRateThrottle

        patched_rates = {**ScopedRateThrottle.THROTTLE_RATES, "ai_feedback": "2/minute"}
        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", patched_rates)

        email1 = incoming_email_factory()
        email2 = incoming_email_factory()
        email3 = incoming_email_factory()

        # Each call must target a distinct row so the upsert path doesn't
        # make all three hit the same DB row — we want to confirm the
        # throttle, not the uniqueness constraint.
        for email in (email1, email2):
            r = subscriber_client.post(
                ENDPOINT,
                {
                    "target_type": "classification",
                    "target_id": str(email.id),
                    "rating": 1,
                },
                format="json",
            )
            assert r.status_code == status.HTTP_201_CREATED

        blocked = subscriber_client.post(
            ENDPOINT,
            {
                "target_type": "classification",
                "target_id": str(email3.id),
                "rating": 1,
            },
            format="json",
        )
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ─── /api/auth/me/ exposes the feature flag ──────────────────────────────


class TestMeFeatureFlag:
    def test_me_returns_ai_thumbs_flag(
        self, subscriber_client: APIClient, settings
    ):
        settings.FEATURE_AI_THUMBS = True
        resp = subscriber_client.get("/api/auth/me/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["features"] == {"ai_thumbs": True}

    def test_me_flag_defaults_off(
        self, subscriber_client: APIClient, settings
    ):
        settings.FEATURE_AI_THUMBS = False
        resp = subscriber_client.get("/api/auth/me/")
        assert resp.json()["features"] == {"ai_thumbs": False}

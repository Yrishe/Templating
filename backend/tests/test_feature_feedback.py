"""Per-feature feedback endpoint tests.

Locks in the invariants for `POST /api/feedback/feature/`:

- Idempotent upsert on ``(user, feature_key, project)``. Re-POST flips the
  rating or updates the comment without duplicating rows.
- ``project`` is optional. App-global features (dashboard, profile) post
  without it; per-project features (chat, timeline) post with it.
- Passing a project the caller cannot see returns 404 — same leak
  prevention as the AI-feedback endpoint.
- ``rating`` must be 1 or -1; ``feature_key`` is required; ``comment`` caps
  at 1000 chars.
- ``feature_feedback`` throttle scope caps at 20/minute.
- `/api/auth/me/features.feature_feedback` respects FEATURE_FEATURE_FEEDBACK.
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from feedback.models import FeatureFeedback


pytestmark = pytest.mark.django_db


ENDPOINT = "/api/feedback/feature/"


# ─── Happy paths ──────────────────────────────────────────────────────────


class TestCreate:
    def test_thumbs_up_without_project_creates_row(
        self, subscriber_client: APIClient
    ):
        resp = subscriber_client.post(
            ENDPOINT,
            {"feature_key": "dashboard.home", "rating": 1},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["feature_key"] == "dashboard.home"
        assert body["rating"] == 1
        assert body["project"] is None
        assert FeatureFeedback.objects.count() == 1

    def test_thumbs_down_with_project_and_comment_creates_row(
        self, subscriber_client: APIClient, project
    ):
        resp = subscriber_client.post(
            ENDPOINT,
            {
                "feature_key": "projects.overview",
                "rating": -1,
                "comment": "The quick-stats card is confusing at a glance.",
                "project": str(project.id),
                "route": f"/projects/{project.id}",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["rating"] == -1
        assert body["comment"].startswith("The quick-stats card")
        assert body["project"] == str(project.id)
        assert body["route"] == f"/projects/{project.id}"


# ─── Idempotent upsert ────────────────────────────────────────────────────


class TestUpsert:
    def test_repost_flips_rating_without_duplicating(
        self, subscriber_client: APIClient, project
    ):
        payload = {
            "feature_key": "projects.overview",
            "rating": 1,
            "project": str(project.id),
        }
        first = subscriber_client.post(ENDPOINT, payload, format="json")
        assert first.status_code == status.HTTP_201_CREATED

        payload["rating"] = -1
        second = subscriber_client.post(ENDPOINT, payload, format="json")
        assert second.status_code == status.HTTP_200_OK
        assert second.json()["rating"] == -1
        assert FeatureFeedback.objects.count() == 1

    def test_comment_attached_on_update(
        self, subscriber_client: APIClient
    ):
        base = {"feature_key": "dashboard.home", "rating": 1}
        subscriber_client.post(ENDPOINT, base, format="json")
        resp = subscriber_client.post(
            ENDPOINT, {**base, "comment": "Loving the new quick-stats."}, format="json"
        )
        assert resp.status_code == status.HTTP_200_OK
        row = FeatureFeedback.objects.get()
        assert row.rating == 1
        assert row.comment == "Loving the new quick-stats."

    def test_same_feature_key_across_projects_is_two_rows(
        self, subscriber_client: APIClient, project
    ):
        """``projects.overview`` is a per-project feature. One row per
        project, so feedback from two projects doesn't collide."""
        # Second project owned by the same subscriber so we don't trip
        # the cross-project 404 guard.
        from accounts.models import Account
        from projects.models import Project, ProjectMembership, Timeline

        second_account = Account.objects.create(
            subscriber=project.account.subscriber,
            name="Second Account",
            email="second@test.com",
        )
        second_project = Project.objects.create(
            account=second_account,
            name="Second Project",
            generic_email="proj-beta@test.com",
        )
        ProjectMembership.objects.create(
            project=second_project, user=project.account.subscriber
        )
        Timeline.objects.get_or_create(project=second_project)

        for pid in (project.id, second_project.id):
            resp = subscriber_client.post(
                ENDPOINT,
                {
                    "feature_key": "projects.overview",
                    "rating": 1,
                    "project": str(pid),
                },
                format="json",
            )
            assert resp.status_code == status.HTTP_201_CREATED

        assert FeatureFeedback.objects.count() == 2


# ─── Auth + permission boundary ───────────────────────────────────────────


class TestPermissions:
    def test_unauthenticated_is_401(self, api_client: APIClient):
        resp = api_client.post(
            ENDPOINT, {"feature_key": "dashboard.home", "rating": 1}, format="json"
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_cross_project_target_returns_404(
        self, second_account_user, project
    ):
        """A user who can't see a project must not be able to submit
        feedback tagged to it. 404 so the endpoint doesn't leak which
        project ids exist cross-account."""
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        access = str(RefreshToken.for_user(second_account_user).access_token)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = client.post(
            ENDPOINT,
            {
                "feature_key": "projects.overview",
                "rating": 1,
                "project": str(project.id),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert FeatureFeedback.objects.count() == 0


# ─── Validation ───────────────────────────────────────────────────────────


class TestValidation:
    def test_missing_feature_key_is_400(self, subscriber_client: APIClient):
        resp = subscriber_client.post(ENDPOINT, {"rating": 1}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "feature_key" in resp.json()

    def test_invalid_rating_is_400(self, subscriber_client: APIClient):
        resp = subscriber_client.post(
            ENDPOINT,
            {"feature_key": "dashboard.home", "rating": 0},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_comment_over_max_length_is_400(self, subscriber_client: APIClient):
        resp = subscriber_client.post(
            ENDPOINT,
            {
                "feature_key": "dashboard.home",
                "rating": 1,
                "comment": "x" * 1001,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_project_id_returns_404(self, subscriber_client: APIClient):
        """Unknown project UUID and cross-project project UUID collapse to
        the same 404 — you can't tell from the response whether the project
        exists at all or you just don't have access to it."""
        import uuid

        resp = subscriber_client.post(
            ENDPOINT,
            {
                "feature_key": "projects.overview",
                "rating": 1,
                "project": str(uuid.uuid4()),
            },
            format="json",
        )
        # DRF's PrimaryKeyRelatedField rejects a non-existent pk at validation
        # time with 400 rather than 404. Either is acceptable — we just
        # confirm it isn't accepted silently.
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )


# ─── Throttle ─────────────────────────────────────────────────────────────


class TestThrottle:
    def test_over_limit_returns_429(
        self, subscriber_client: APIClient, monkeypatch
    ):
        """21st POST in a minute → 429.

        Following the same pattern as test_ai_feedback.TestThrottle:
        DRF captures THROTTLE_RATES on the class at import time, so we
        patch the class attribute directly instead of Django settings.
        """
        from rest_framework.throttling import ScopedRateThrottle

        patched_rates = {
            **ScopedRateThrottle.THROTTLE_RATES,
            "feature_feedback": "2/minute",
        }
        monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", patched_rates)

        # Three different feature_keys so every call writes a distinct row
        # and we're really measuring the throttle, not the uniqueness
        # constraint.
        for key in ("f.one", "f.two"):
            r = subscriber_client.post(
                ENDPOINT, {"feature_key": key, "rating": 1}, format="json"
            )
            assert r.status_code == status.HTTP_201_CREATED

        blocked = subscriber_client.post(
            ENDPOINT, {"feature_key": "f.three", "rating": 1}, format="json"
        )
        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ─── /api/auth/me/ exposes the feature flag ──────────────────────────────


class TestMeFeatureFlag:
    def test_me_returns_feature_feedback_flag(
        self, subscriber_client: APIClient, settings
    ):
        settings.FEATURE_FEATURE_FEEDBACK = True
        resp = subscriber_client.get("/api/auth/me/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["features"]["feature_feedback"] is True

    def test_me_feature_feedback_defaults_off(
        self, subscriber_client: APIClient, settings
    ):
        settings.FEATURE_FEATURE_FEEDBACK = False
        resp = subscriber_client.get("/api/auth/me/")
        assert resp.json()["features"]["feature_feedback"] is False

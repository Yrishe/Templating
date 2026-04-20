"""Tests for the 3-stage AI email classification pipeline and related endpoints.

All Claude API calls are mocked — no real Anthropic requests are made.
Tests use CELERY_TASK_ALWAYS_EAGER so tasks run inline.
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.utils import timezone

from email_organiser.models import EmailAnalysis, IncomingEmail
from notifications.models import Notification
from projects.models import TimelineEvent


# ─── Helpers ──────────────────────────────────────────────────────────


def _mock_claude_response(text: str):
    """Build a mock Anthropic Messages.create response."""
    mock_block = MagicMock()
    mock_block.text = text
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    return mock_response


def _mock_anthropic_client(responses: list[str]):
    """Return a mock Anthropic class whose create() returns the given texts in order."""
    client = MagicMock()
    side_effects = [_mock_claude_response(t) for t in responses]
    client.return_value.messages.create.side_effect = side_effects
    return client


# ═══════════════════════════════════════════════════════════════════════
# Stage 1 — classify_incoming_email
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestClassifyIncomingEmail:
    def test_relevant_email_classified_and_chains_to_stage2(
        self, incoming_email_factory, contract_with_text
    ):
        email = incoming_email_factory()
        classification_json = json.dumps({
            "is_relevant": True,
            "relevance": "high",
            "category": "delay",
            "keywords": ["delivery", "delay", "supply chain"],
        })

        mock_client = _mock_anthropic_client([classification_json])

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = classification_json
            with patch("email_organiser.tasks.analyse_email_by_topic") as mock_stage2:
                mock_stage2.delay = MagicMock()

                from email_organiser.tasks import classify_incoming_email
                classify_incoming_email.run(str(email.pk))

                email.refresh_from_db()
                assert email.is_relevant is True
                assert email.relevance == "high"
                assert email.category == "delay"
                assert "delivery" in email.keywords
                assert email.is_processed is False  # stage 2 hasn't run yet
                mock_stage2.delay.assert_called_once_with(str(email.pk))

    def test_irrelevant_email_marked_processed_no_stage2(
        self, incoming_email_factory
    ):
        email = incoming_email_factory(
            subject="Weekly newsletter",
            body_plain="Check out our latest blog post about gardening tips!",
        )
        classification_json = json.dumps({
            "is_relevant": False,
            "relevance": "none",
            "category": "irrelevant",
            "keywords": ["newsletter", "blog"],
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = classification_json
            with patch("email_organiser.tasks.analyse_email_by_topic") as mock_stage2:
                mock_stage2.delay = MagicMock()

                from email_organiser.tasks import classify_incoming_email
                classify_incoming_email.run(str(email.pk))

                email.refresh_from_db()
                assert email.is_relevant is False
                assert email.category == "irrelevant"
                assert email.is_processed is True
                mock_stage2.delay.assert_not_called()

    def test_no_api_key_falls_back_to_defaults(self, incoming_email_factory):
        email = incoming_email_factory()

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = None  # simulate no API key
            with patch("email_organiser.tasks.analyse_email_by_topic") as mock_stage2:
                mock_stage2.delay = MagicMock()

                from email_organiser.tasks import classify_incoming_email
                classify_incoming_email.run(str(email.pk))

                email.refresh_from_db()
                assert email.is_relevant is True
                assert email.relevance == "medium"
                assert email.category == "general"
                # Should still chain to stage 2
                mock_stage2.delay.assert_called_once()

    def test_malformed_json_falls_back_to_defaults(self, incoming_email_factory):
        email = incoming_email_factory()

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = "not valid json {{"
            with patch("email_organiser.tasks.analyse_email_by_topic") as mock_stage2:
                mock_stage2.delay = MagicMock()

                from email_organiser.tasks import classify_incoming_email
                classify_incoming_email.run(str(email.pk))

                email.refresh_from_db()
                assert email.relevance == "medium"
                assert email.category == "general"
                mock_stage2.delay.assert_called_once()

    def test_invalid_category_normalized_to_general(self, incoming_email_factory):
        email = incoming_email_factory()
        classification_json = json.dumps({
            "is_relevant": True,
            "relevance": "high",
            "category": "nonexistent_category",
            "keywords": [],
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = classification_json
            with patch("email_organiser.tasks.analyse_email_by_topic") as mock_stage2:
                mock_stage2.delay = MagicMock()

                from email_organiser.tasks import classify_incoming_email
                classify_incoming_email.run(str(email.pk))

                email.refresh_from_db()
                assert email.category == "general"


# ═══════════════════════════════════════════════════════════════════════
# Stage 2 — analyse_email_by_topic
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAnalyseEmailByTopic:
    def test_creates_email_analysis(self, incoming_email_factory, contract_with_text):
        email = incoming_email_factory()
        email.category = "delay"
        email.relevance = "high"
        email.save()

        analysis_json = json.dumps({
            "risk_level": "high",
            "risk_summary": "Supplier delay of 2 weeks will push milestone.",
            "contract_references": "Section 3 - Delay Clause",
            "mitigation": "Invoke force majeure if applicable.",
            "suggested_response": "Request written notice with new delivery date.",
            "resolution_path": "1. Verify cause. 2. Issue formal response.",
            "timeline_impact": "Project completion delayed by 2 weeks minimum.",
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = analysis_json
            with patch("email_organiser.tasks.generate_timeline_event_from_email") as mock_stage3:
                mock_stage3.delay = MagicMock()
                with patch("notifications.tasks.create_email_occurrence_notification") as mock_notif:
                    mock_notif.delay = MagicMock()

                    from email_organiser.tasks import analyse_email_by_topic
                    analyse_email_by_topic.run(str(email.pk))

                    analysis = EmailAnalysis.objects.get(email=email)
                    assert analysis.risk_level == "high"
                    assert "Supplier delay" in analysis.risk_summary
                    assert "Section 3" in analysis.contract_references
                    assert analysis.agent_topic == "delay"
                    mock_stage3.delay.assert_called_once()
                    # High relevance → notification
                    mock_notif.delay.assert_called_once()

    def test_medium_relevance_no_notification(self, incoming_email_factory, contract_with_text):
        email = incoming_email_factory()
        email.category = "general"
        email.relevance = "medium"
        email.save()

        analysis_json = json.dumps({
            "risk_level": "low",
            "risk_summary": "General inquiry.",
            "contract_references": "",
            "mitigation": "",
            "suggested_response": "Acknowledge receipt.",
            "resolution_path": "",
            "timeline_impact": "none",
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = analysis_json
            with patch("email_organiser.tasks.generate_timeline_event_from_email") as mock_stage3:
                mock_stage3.delay = MagicMock()
                with patch("notifications.tasks.create_email_occurrence_notification") as mock_notif:
                    mock_notif.delay = MagicMock()

                    from email_organiser.tasks import analyse_email_by_topic
                    analyse_email_by_topic.run(str(email.pk))

                    mock_notif.delay.assert_not_called()

    def test_no_contract_still_runs(self, incoming_email_factory, project):
        """Analysis should work even without a contract — graceful fallback."""
        email = incoming_email_factory()
        email.category = "costs"
        email.save()

        analysis_json = json.dumps({
            "risk_level": "medium",
            "risk_summary": "Cost increase flagged but no contract to reference.",
            "contract_references": "No contract available.",
            "mitigation": "",
            "suggested_response": "",
            "resolution_path": "",
            "timeline_impact": "",
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = analysis_json
            with patch("email_organiser.tasks.generate_timeline_event_from_email") as mock_stage3:
                mock_stage3.delay = MagicMock()

                from email_organiser.tasks import analyse_email_by_topic
                analyse_email_by_topic.run(str(email.pk))

                assert EmailAnalysis.objects.filter(email=email).exists()


# ═══════════════════════════════════════════════════════════════════════
# Stage 3 — generate_timeline_event_from_email
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGenerateTimelineEvent:
    def test_creates_timeline_event_and_links_analysis(
        self, incoming_email_factory, contract_with_text
    ):
        email = incoming_email_factory()
        email.category = "delay"
        email.relevance = "high"
        email.save()

        analysis = EmailAnalysis.objects.create(
            email=email,
            agent_topic="delay",
            risk_level="high",
            risk_summary="2-week delivery delay.",
            timeline_impact="Pushes milestone by 2 weeks.",
            mitigation="Invoke force majeure.",
        )

        timeline_json = json.dumps({
            "title": "Review delivery delay from Acme Supplier",
            "description": "Supplier notified 2-week delay due to supply chain issues.",
            "priority": "high",
            "deadline_days": 5,
        })

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = timeline_json

            from email_organiser.tasks import generate_timeline_event_from_email
            generate_timeline_event_from_email.run(str(email.pk))

            email.refresh_from_db()
            assert email.is_processed is True

            analysis.refresh_from_db()
            assert analysis.generated_timeline_event is not None

            event = analysis.generated_timeline_event
            assert "delay" in event.title.lower() or "delivery" in event.title.lower()
            assert event.priority == "high"
            assert event.status == TimelineEvent.PLANNED
            assert event.end_date is not None

    def test_fallback_event_when_claude_unavailable(
        self, incoming_email_factory, contract_with_text
    ):
        email = incoming_email_factory(subject="Cost escalation notice")
        email.category = "costs"
        email.save()

        EmailAnalysis.objects.create(
            email=email,
            agent_topic="costs",
            risk_level="medium",
            risk_summary="Cost increase of 15%.",
        )

        with patch("email_organiser.tasks._call_claude") as mock_call:
            mock_call.return_value = None  # Claude unavailable

            from email_organiser.tasks import generate_timeline_event_from_email
            generate_timeline_event_from_email.run(str(email.pk))

            email.refresh_from_db()
            assert email.is_processed is True

            analysis = EmailAnalysis.objects.get(email=email)
            assert analysis.generated_timeline_event is not None
            event = analysis.generated_timeline_event
            assert "Costs" in event.title or "Cost" in event.title

    def test_no_analysis_marks_processed(self, incoming_email_factory):
        email = incoming_email_factory()
        # No EmailAnalysis created

        from email_organiser.tasks import generate_timeline_event_from_email
        generate_timeline_event_from_email.run(str(email.pk))

        email.refresh_from_db()
        assert email.is_processed is True
        assert TimelineEvent.objects.count() == 0


# ═══════════════════════════════════════════════════════════════════════
# Webhook tests
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestInboundEmailWebhook:
    WEBHOOK_URL = "/api/webhooks/inbound-email/"

    def test_missing_secret_returns_401(self, api_client, project):
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            resp = api_client.post(
                self.WEBHOOK_URL,
                data={"to": project.generic_email, "message_id": "<1@test>"},
                format="json",
            )
            assert resp.status_code == 401

    def test_wrong_secret_returns_401(self, api_client, project):
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            resp = api_client.post(
                self.WEBHOOK_URL,
                data={"to": project.generic_email, "message_id": "<1@test>"},
                format="json",
                HTTP_X_WEBHOOK_SECRET="wrong-secret",
            )
            assert resp.status_code == 401

    def test_unknown_to_address_returns_404(self, api_client):
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            resp = api_client.post(
                self.WEBHOOK_URL,
                data={
                    "to": "nonexistent@inbound.contractmgr.app",
                    "message_id": "<1@test>",
                    "from": "sender@test.com",
                    "body_plain": "test",
                },
                format="json",
                HTTP_X_WEBHOOK_SECRET="test-secret",
            )
            assert resp.status_code == 404

    def test_valid_webhook_creates_email_and_enqueues_pipeline(self, api_client, project):
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            # Patch at the task's source module — the view imports it
            # lazily inside the handler, so the name never exists on the
            # `views` module namespace to be patched there.
            with patch("email_organiser.tasks.classify_incoming_email") as mock_classify:
                mock_classify.delay = MagicMock()
                with patch("notifications.tasks.create_incoming_email_notification") as mock_notif:
                    mock_notif.delay = MagicMock()

                    resp = api_client.post(
                        self.WEBHOOK_URL,
                        data={
                            "to": project.generic_email,
                            "from": "client@example.com",
                            "from_name": "Client",
                            "subject": "Re: Contract terms",
                            "body_plain": "We need to discuss the delay clause.",
                            "message_id": "<unique-1@test.com>",
                        },
                        format="json",
                        HTTP_X_WEBHOOK_SECRET="test-secret",
                    )
                    assert resp.status_code == 201
                    assert IncomingEmail.objects.filter(
                        project=project, message_id="<unique-1@test.com>"
                    ).exists()
                    mock_classify.delay.assert_called_once()

    def test_duplicate_message_id_returns_200(self, api_client, project):
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            IncomingEmail.objects.create(
                project=project,
                sender_email="client@example.com",
                message_id="<dup@test.com>",
                received_at=timezone.now(),
            )
            resp = api_client.post(
                self.WEBHOOK_URL,
                data={
                    "to": project.generic_email,
                    "from": "client@example.com",
                    "message_id": "<dup@test.com>",
                    "body_plain": "test",
                },
                format="json",
                HTTP_X_WEBHOOK_SECRET="test-secret",
            )
            assert resp.status_code == 200
            assert IncomingEmail.objects.filter(message_id="<dup@test.com>").count() == 1

    def test_pipeline_enqueue_failure_still_returns_201(self, api_client, project):
        """Graceful degradation: pipeline failure shouldn't fail the webhook."""
        with self.settings(INBOUND_EMAIL_WEBHOOK_SECRET="test-secret"):
            with patch("email_organiser.tasks.classify_incoming_email") as mock_classify:
                mock_classify.delay.side_effect = Exception("Broker down")
                with patch("notifications.tasks.create_incoming_email_notification") as mock_notif:
                    mock_notif.delay = MagicMock()

                    resp = api_client.post(
                        self.WEBHOOK_URL,
                        data={
                            "to": project.generic_email,
                            "from": "client@example.com",
                            "message_id": "<fail-1@test.com>",
                            "body_plain": "test",
                        },
                        format="json",
                        HTTP_X_WEBHOOK_SECRET="test-secret",
                    )
                    assert resp.status_code == 201

    @staticmethod
    def settings(**kwargs):
        """Helper to override Django settings in tests."""
        from django.test import override_settings
        return override_settings(**kwargs)


# ═══════════════════════════════════════════════════════════════════════
# Endpoint tests — resolve, reanalyse, filter
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmailEndpoints:
    def test_resolve_marks_email_resolved(
        self, manager_client, project, incoming_email_factory
    ):
        email = incoming_email_factory()
        assert email.is_resolved is False

        resp = manager_client.post(
            f"/api/projects/{project.pk}/incoming-emails/{email.pk}/resolve/"
        )
        assert resp.status_code == 200
        email.refresh_from_db()
        assert email.is_resolved is True

    def test_reanalyse_resets_and_enqueues(
        self, manager_client, project, incoming_email_factory
    ):
        email = incoming_email_factory()
        email.is_processed = True
        email.save()
        EmailAnalysis.objects.create(
            email=email, agent_topic="delay", risk_level="medium"
        )

        with patch("email_organiser.tasks.classify_incoming_email") as mock_classify:
            mock_classify.delay = MagicMock()

            resp = manager_client.post(
                f"/api/projects/{project.pk}/incoming-emails/{email.pk}/reanalyse/"
            )
            assert resp.status_code == 202
            email.refresh_from_db()
            assert email.is_processed is False
            assert not EmailAnalysis.objects.filter(email=email).exists()
            mock_classify.delay.assert_called_once()

    def test_list_filter_by_category(
        self, manager_client, project, incoming_email_factory
    ):
        e1 = incoming_email_factory()
        e1.category = "costs"
        e1.is_relevant = True
        e1.save()

        e2 = incoming_email_factory()
        e2.category = "delay"
        e2.is_relevant = True
        e2.save()

        resp = manager_client.get(
            f"/api/projects/{project.pk}/incoming-emails/?category=costs&is_relevant=true"
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert str(e1.pk) in ids
        assert str(e2.pk) not in ids

    def test_list_filter_by_relevance(
        self, manager_client, project, incoming_email_factory
    ):
        e1 = incoming_email_factory()
        e1.relevance = "high"
        e1.is_relevant = True
        e1.save()

        e2 = incoming_email_factory()
        e2.relevance = "low"
        e2.is_relevant = True
        e2.save()

        resp = manager_client.get(
            f"/api/projects/{project.pk}/incoming-emails/?relevance=high&is_relevant=true"
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.data["results"]]
        assert str(e1.pk) in ids
        assert str(e2.pk) not in ids

    def test_non_member_cannot_access(self, invited_client, project, incoming_email_factory):
        email = incoming_email_factory()
        resp = invited_client.get(
            f"/api/projects/{project.pk}/incoming-emails/"
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# Notification tasks
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotificationTasks:
    def test_email_occurrence_notification_created(
        self, incoming_email_factory, project
    ):
        email = incoming_email_factory()

        from notifications.tasks import create_email_occurrence_notification
        create_email_occurrence_notification.run(str(email.pk))

        notif = Notification.objects.get(
            project=project, type=Notification.EMAIL_HIGH_RELEVANCE
        )
        assert notif is not None

    def test_unresolved_occurrences_flagged(self, incoming_email_factory, project):
        email = incoming_email_factory()
        email.is_relevant = True
        email.is_resolved = False
        email.is_processed = True
        email.received_at = timezone.now() - timedelta(hours=72)
        email.save()

        from notifications.tasks import check_unresolved_email_occurrences
        created = check_unresolved_email_occurrences.run()

        assert created == 1
        assert Notification.objects.filter(
            project=project, type=Notification.EMAIL_OCCURRENCE_UNRESOLVED
        ).exists()

    def test_unresolved_deduplication(self, incoming_email_factory, project):
        email = incoming_email_factory()
        email.is_relevant = True
        email.is_resolved = False
        email.is_processed = True
        email.received_at = timezone.now() - timedelta(hours=72)
        email.save()

        from notifications.tasks import check_unresolved_email_occurrences
        check_unresolved_email_occurrences.run()
        created = check_unresolved_email_occurrences.run()  # second run

        assert created == 0  # deduped
        assert Notification.objects.filter(
            project=project, type=Notification.EMAIL_OCCURRENCE_UNRESOLVED
        ).count() == 1

    def test_resolved_email_not_flagged(self, incoming_email_factory, project):
        email = incoming_email_factory()
        email.is_relevant = True
        email.is_resolved = True  # resolved
        email.is_processed = True
        email.received_at = timezone.now() - timedelta(hours=72)
        email.save()

        from notifications.tasks import check_unresolved_email_occurrences
        created = check_unresolved_email_occurrences.run()

        assert created == 0

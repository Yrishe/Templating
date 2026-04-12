"""Notification feed tests.

Locks in the recent behavior changes:

- **Actor suppression** — a user never sees notifications they caused.
  Uses a Q-object form so NULL-actor notifications (new_email,
  deadline_upcoming, legacy rows) still pass through, which plain
  `.exclude(actor=user)` would have dropped (Django nullable-FK footgun).
- **Per-user dismissal** — `read_by` M2M. Clicking = add self to read_by.
  The row stays visible to everyone else.
- **New notification types** — contract_request_approved/_rejected,
  new_email, deadline_upcoming.
- **Manager visibility** — managers see notifications from every project
  (same oversight rule as projects / contracts).
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification


pytestmark = pytest.mark.django_db


# ─── Actor suppression ────────────────────────────────────────────────────


class TestActorSuppression:
    def test_user_does_not_see_own_notification(
        self, subscriber_client: APIClient, project, subscriber_user
    ):
        """Notification with actor=subscriber must NOT appear in subscriber's feed."""
        Notification.objects.create(
            project=project,
            type=Notification.CONTRACT_REQUEST,
            actor=subscriber_user,
        )
        resp = subscriber_client.get(f"/api/notifications/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 0

    def test_other_user_sees_the_notification(
        self,
        subscriber_client: APIClient,
        manager_client: APIClient,
        project,
        subscriber_user,
    ):
        """Same row should show up in the MANAGER's feed (they're another member)."""
        Notification.objects.create(
            project=project,
            type=Notification.CONTRACT_REQUEST,
            actor=subscriber_user,
        )
        resp = manager_client.get(f"/api/notifications/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1

    def test_null_actor_notification_is_not_dropped(
        self, subscriber_client: APIClient, project
    ):
        """Regression for the Django `.exclude(actor=user)` footgun.

        A notification with actor=NULL (e.g. new_email from an external
        sender) must still appear in every member's feed. Plain
        `.exclude(actor=user)` would generate WHERE NOT (actor_id = %s),
        which is NULL for NULL actor rows and treated as FALSE by
        Postgres — silently dropping them. The Q-object form preserves
        them.
        """
        Notification.objects.create(
            project=project, type=Notification.NEW_EMAIL, actor=None
        )
        resp = subscriber_client.get(f"/api/notifications/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1

    def test_deadline_upcoming_with_null_actor_is_visible(
        self, subscriber_client: APIClient, project
    ):
        Notification.objects.create(
            project=project, type=Notification.DEADLINE_UPCOMING, actor=None
        )
        resp = subscriber_client.get(f"/api/notifications/?project={project.id}")
        assert resp.json()["count"] == 1


# ─── Per-user dismissal ───────────────────────────────────────────────────


class TestPerUserDismissal:
    def test_mark_read_dismisses_only_for_the_clicker(
        self,
        subscriber_client: APIClient,
        manager_client: APIClient,
        project,
        manager_user,
    ):
        """User A clicks a notification → it disappears from A's feed,
        but User B still sees it."""
        n = Notification.objects.create(
            project=project,
            type=Notification.CONTRACT_REQUEST,
            actor=manager_user,  # so subscriber (the clicker) CAN see it
        )
        # Before: subscriber can see it
        resp = subscriber_client.get(f"/api/notifications/?project={project.id}")
        assert resp.json()["count"] == 1

        # Click (mark as read)
        subscriber_client.post(f"/api/notifications/{n.id}/read/")

        # Subscriber no longer sees it
        resp2 = subscriber_client.get(f"/api/notifications/?project={project.id}")
        assert resp2.json()["count"] == 0
        # But the row is still in the DB
        assert Notification.objects.filter(pk=n.id).exists()

    def test_mark_all_read_only_dismisses_for_the_clicker(
        self,
        subscriber_client: APIClient,
        manager_client: APIClient,
        project,
    ):
        """Mark-all-read affects only the clicker's view, not globally.

        Use `actor=None` notifications (the shape of new_email /
        deadline_upcoming) so both users can see them — the actor
        suppression filter can't interfere with the invariant we're
        actually testing here.
        """
        Notification.objects.create(
            project=project, type=Notification.NEW_EMAIL, actor=None
        )
        Notification.objects.create(
            project=project, type=Notification.DEADLINE_UPCOMING, actor=None
        )

        # Before: both users see both rows.
        assert (
            subscriber_client.get(f"/api/notifications/?project={project.id}")
            .json()["count"]
            == 2
        )
        assert (
            manager_client.get(f"/api/notifications/?project={project.id}")
            .json()["count"]
            == 2
        )

        # Subscriber dismisses everything from their feed.
        subscriber_client.post("/api/notifications/mark-all-read/")

        # Subscriber's feed is now empty…
        assert (
            subscriber_client.get(f"/api/notifications/?project={project.id}")
            .json()["count"]
            == 0
        )
        # …but the manager still sees both rows. That's the invariant —
        # read_by is per-user, so one user clicking mark-all-read doesn't
        # affect anyone else.
        assert (
            manager_client.get(f"/api/notifications/?project={project.id}")
            .json()["count"]
            == 2
        )


# ─── Manager oversight ───────────────────────────────────────────────────


class TestManagerOversight:
    def test_manager_sees_notifications_on_non_member_projects(
        self,
        manager_client: APIClient,
        api_client: APIClient,
        second_account_user,
        project,
        subscriber_user,
    ):
        """A manager who isn't a ProjectMembership row on a given project
        should still see its notifications (oversight model)."""
        # Build a second project that the manager is NOT a member of.
        from accounts.models import Account
        from projects.models import Project, ProjectMembership
        account2 = Account.objects.create(
            subscriber=second_account_user,
            name="Alt",
            email="alt@test.com",
        )
        project2 = Project.objects.create(
            account=account2,
            name="Second Project",
            generic_email="proj-second@test.com",
        )
        ProjectMembership.objects.create(project=project2, user=second_account_user)

        Notification.objects.create(
            project=project2,
            type=Notification.CONTRACT_REQUEST,
            actor=second_account_user,
        )
        resp = manager_client.get(f"/api/notifications/?project={project2.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1


# ─── New notification types render ───────────────────────────────────────


class TestNotificationTypes:
    @pytest.mark.parametrize(
        "ntype",
        [
            Notification.CONTRACT_REQUEST,
            Notification.CONTRACT_REQUEST_APPROVED,
            Notification.CONTRACT_REQUEST_REJECTED,
            Notification.CONTRACT_UPDATE,
            Notification.CHAT_MESSAGE,
            Notification.NEW_EMAIL,
            Notification.DEADLINE_UPCOMING,
        ],
    )
    def test_every_type_round_trips_through_the_feed(
        self,
        subscriber_client: APIClient,
        project,
        manager_user,
        ntype,
    ):
        """Sanity: every new type value is accepted by the model and the
        serializer exposes it unchanged on the feed endpoint."""
        Notification.objects.create(project=project, type=ntype, actor=manager_user)
        resp = subscriber_client.get(f"/api/notifications/?project={project.id}")
        types = [n["type"] for n in resp.json()["results"]]
        assert ntype in types

"""Permission boundary tests for project / contract / membership endpoints.

These lock in the "managers see all projects" oversight rule we added to
fix the 404 that hit a manager clicking into a project they didn't
personally create.
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Account, User
from projects.models import Project, ProjectMembership


pytestmark = pytest.mark.django_db


# ─── Project list / detail visibility ─────────────────────────────────────


class TestProjectVisibility:
    def test_account_sees_only_own_project(
        self, subscriber_client: APIClient, project: Project
    ):
        resp = subscriber_client.get("/api/projects/")
        assert resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in resp.json()["results"]]
        assert str(project.id) in ids

    def test_account_cannot_see_other_account_project(
        self,
        api_client: APIClient,
        second_account_user: User,
        project: Project,
    ):
        """A different account user (who isn't a member) should not see the project."""
        from rest_framework_simplejwt.tokens import RefreshToken
        access = str(RefreshToken.for_user(second_account_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        list_resp = api_client.get("/api/projects/")
        assert list_resp.status_code == status.HTTP_200_OK
        ids = [p["id"] for p in list_resp.json()["results"]]
        assert str(project.id) not in ids

        detail_resp = api_client.get(f"/api/projects/{project.id}/")
        assert detail_resp.status_code == status.HTTP_404_NOT_FOUND

    def test_manager_sees_every_project(
        self, manager_client: APIClient, project: Project
    ):
        """Managers have oversight on every project regardless of membership.

        This is the fix that resolved the 404 a manager saw when clicking
        into a project they didn't personally create.
        """
        resp = manager_client.get(f"/api/projects/{project.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["id"] == str(project.id)

    def test_unauthenticated_cannot_see_any_project(
        self, api_client: APIClient, project: Project
    ):
        resp = api_client.get(f"/api/projects/{project.id}/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ─── Contract list visibility ─────────────────────────────────────────────


class TestContractVisibility:
    def test_manager_sees_every_projects_contracts(
        self,
        manager_client: APIClient,
        project: Project,
        subscriber_user: User,
    ):
        """Regression for the 'contracts list filtered by membership' bug
        that caused the POST→upsert race on the contract upload form."""
        # Create a contract as the subscriber
        from contracts.models import Contract
        Contract.objects.create(
            project=project, title="C1", created_by=subscriber_user
        )
        resp = manager_client.get(f"/api/contracts/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 1

    def test_non_member_account_does_not_see_other_projects_contracts(
        self,
        api_client: APIClient,
        second_account_user: User,
        project: Project,
        subscriber_user: User,
    ):
        from contracts.models import Contract
        from rest_framework_simplejwt.tokens import RefreshToken

        Contract.objects.create(
            project=project, title="C1", created_by=subscriber_user
        )
        access = str(RefreshToken.for_user(second_account_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = api_client.get(f"/api/contracts/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 0


# ─── Contract mutation permissions ────────────────────────────────────────


class TestContractMutationPermissions:
    def test_account_can_update_own_contract(
        self,
        subscriber_client: APIClient,
        project: Project,
        subscriber_user: User,
    ):
        """Regression for the 'Only managers can edit contracts' stale gate.
        Account users are supposed to be able to PATCH their own contract.
        """
        from contracts.models import Contract
        contract = Contract.objects.create(
            project=project, title="Old title", created_by=subscriber_user
        )
        resp = subscriber_client.patch(
            f"/api/contracts/{contract.id}/",
            {"title": "New title"},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.title == "New title"

    def test_invited_user_cannot_update_contract(
        self,
        api_client: APIClient,
        project: Project,
        subscriber_user: User,
        invited_user: User,
    ):
        """Invited-account users can raise change requests but not edit the
        contract directly."""
        from contracts.models import Contract
        from rest_framework_simplejwt.tokens import RefreshToken
        contract = Contract.objects.create(
            project=project, title="Old", created_by=subscriber_user
        )
        ProjectMembership.objects.get_or_create(project=project, user=invited_user)
        access = str(RefreshToken.for_user(invited_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = api_client.patch(
            f"/api/contracts/{contract.id}/",
            {"title": "Hacked"},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_only_manager_can_activate_contract(
        self,
        subscriber_client: APIClient,
        manager_client: APIClient,
        project: Project,
        subscriber_user: User,
    ):
        from contracts.models import Contract
        contract = Contract.objects.create(
            project=project,
            title="C",
            created_by=subscriber_user,
            status=Contract.DRAFT,
        )
        # Account cannot activate
        bad = subscriber_client.post(f"/api/contracts/{contract.id}/activate/")
        assert bad.status_code == status.HTTP_403_FORBIDDEN
        # Manager can
        good = manager_client.post(f"/api/contracts/{contract.id}/activate/")
        assert good.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.status == Contract.ACTIVE


# ─── Project membership list visibility ───────────────────────────────────


class TestProjectMembershipVisibility:
    def test_account_sees_only_own_project_memberships(
        self, subscriber_client: APIClient, project: Project
    ):
        resp = subscriber_client.get(
            f"/api/project-memberships/?project={project.id}"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] >= 1

    def test_non_member_account_sees_empty_membership_list(
        self,
        api_client: APIClient,
        second_account_user: User,
        project: Project,
    ):
        from rest_framework_simplejwt.tokens import RefreshToken
        access = str(RefreshToken.for_user(second_account_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = api_client.get(f"/api/project-memberships/?project={project.id}")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 0

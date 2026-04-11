"""Contract upload + update tests.

Covers the validated file upload path (PDF magic-byte + size cap),
the POST-is-idempotent upsert behavior we added to stop the stale-cache
unique-constraint race, and the account-can-update-own-contract rule.
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


# ─── Upload / create ──────────────────────────────────────────────────────


class TestContractUpload:
    def test_account_uploads_valid_pdf(
        self,
        subscriber_client: APIClient,
        project,
        valid_pdf_upload,
    ):
        resp = subscriber_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Vendor Agreement",
                "file": valid_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["title"] == "Vendor Agreement"
        assert body["project"] == str(project.id)

    def test_upload_non_pdf_is_rejected(
        self,
        subscriber_client: APIClient,
        project,
        not_a_pdf_upload,
    ):
        resp = subscriber_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Bogus",
                "file": not_a_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "file" in resp.json()

    def test_upload_oversized_pdf_is_rejected(
        self,
        subscriber_client: APIClient,
        project,
        oversized_pdf_upload,
    ):
        resp = subscriber_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Too big",
                "file": oversized_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "file" in resp.json()

    def test_post_is_idempotent_when_contract_already_exists(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
        valid_pdf_upload,
    ):
        """Regression for the 'contract with this project already exists' 400.

        After the upsert fix, POST /api/contracts/ with a project that
        already has a contract should update the existing row (200 OK)
        rather than fail on the OneToOne unique constraint.
        """
        from contracts.models import Contract
        Contract.objects.create(
            project=project, title="Initial", created_by=subscriber_user
        )
        resp = subscriber_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Replacement",
                "file": valid_pdf_upload,
            },
            format="multipart",
        )
        # Upsert returns 200 OK (not 201) when the existing row is updated.
        assert resp.status_code == status.HTTP_200_OK
        assert Contract.objects.filter(project=project).count() == 1
        contract = Contract.objects.get(project=project)
        assert contract.title == "Replacement"

    def test_manager_can_upload_contract_on_any_project(
        self,
        manager_client: APIClient,
        project,
        valid_pdf_upload,
    ):
        """Managers get upload rights via the (account, manager) allow-list."""
        resp = manager_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Manager upload",
                "file": valid_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED

    def test_invited_user_cannot_upload_contract(
        self,
        api_client: APIClient,
        project,
        invited_user,
        valid_pdf_upload,
    ):
        from projects.models import ProjectMembership
        from rest_framework_simplejwt.tokens import RefreshToken
        ProjectMembership.objects.get_or_create(project=project, user=invited_user)
        access = str(RefreshToken.for_user(invited_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = api_client.post(
            "/api/contracts/",
            {
                "project": str(project.id),
                "title": "Nope",
                "file": valid_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ─── Activation ───────────────────────────────────────────────────────────


class TestContractActivation:
    def test_activate_flips_draft_to_active(
        self,
        manager_client: APIClient,
        project,
        subscriber_user,
    ):
        from contracts.models import Contract
        contract = Contract.objects.create(
            project=project,
            title="T",
            created_by=subscriber_user,
            status=Contract.DRAFT,
        )
        resp = manager_client.post(f"/api/contracts/{contract.id}/activate/")
        assert resp.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        assert contract.status == Contract.ACTIVE
        assert contract.activated_at is not None

    def test_activate_is_rejected_when_already_active(
        self,
        manager_client: APIClient,
        project,
        subscriber_user,
    ):
        from contracts.models import Contract
        from django.utils import timezone
        contract = Contract.objects.create(
            project=project,
            title="T",
            created_by=subscriber_user,
            status=Contract.ACTIVE,
            activated_at=timezone.now(),
        )
        resp = manager_client.post(f"/api/contracts/{contract.id}/activate/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

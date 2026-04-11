"""Contract change request lifecycle tests.

Locks in:
- Only Account-type users (account / invited_account who are members) can raise
- Managers CANNOT raise (403)
- project.account is auto-assigned server-side (client-supplied value ignored)
- Optional attachment passes through PDF + size validators
- Approve / reject accept a `review_comment` and persist it
- Approve auto-activates a draft contract
- Reject no longer silent (was a bug; now emits a notification)
- Multiple pending requests are allowed on the same project
"""
from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def _create_contract_in_draft(project, creator):
    from contracts.models import Contract
    return Contract.objects.create(
        project=project,
        title="T",
        created_by=creator,
        status=Contract.DRAFT,
    )


# ─── Raise ────────────────────────────────────────────────────────────────


class TestRaiseChangeRequest:
    def test_account_can_raise_request_with_attachment(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
        valid_pdf_upload,
    ):
        _create_contract_in_draft(project, subscriber_user)
        resp = subscriber_client.post(
            "/api/contract-requests/",
            {
                "project": str(project.id),
                "description": "Please update clause 4",
                "attachment": valid_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["status"] == "pending"
        assert body["description"] == "Please update clause 4"
        # account field is read-only + server-assigned
        assert body["account"] is not None
        assert body["attachment"]

    def test_account_can_raise_request_without_attachment(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        _create_contract_in_draft(project, subscriber_user)
        resp = subscriber_client.post(
            "/api/contract-requests/",
            {
                "project": str(project.id),
                "description": "Clause 4 wording tweak",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["status"] == "pending"

    def test_manager_cannot_raise_request(
        self,
        manager_client: APIClient,
        project,
        subscriber_user,
    ):
        """Managers review, they don't raise."""
        _create_contract_in_draft(project, subscriber_user)
        resp = manager_client.post(
            "/api/contract-requests/",
            {"project": str(project.id), "description": "Nope"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_non_member_cannot_raise_request(
        self,
        api_client: APIClient,
        project,
        second_account_user,
        subscriber_user,
    ):
        """Account user not in the project's membership list → 403."""
        from rest_framework_simplejwt.tokens import RefreshToken
        _create_contract_in_draft(project, subscriber_user)
        access = str(RefreshToken.for_user(second_account_user).access_token)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = api_client.post(
            "/api/contract-requests/",
            {"project": str(project.id), "description": "Drive-by"},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_attachment_rejects_non_pdf(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
        not_a_pdf_upload,
    ):
        _create_contract_in_draft(project, subscriber_user)
        resp = subscriber_client.post(
            "/api/contract-requests/",
            {
                "project": str(project.id),
                "description": "desc",
                "attachment": not_a_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "attachment" in resp.json()

    def test_attachment_rejects_oversized(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
        oversized_pdf_upload,
    ):
        _create_contract_in_draft(project, subscriber_user)
        resp = subscriber_client.post(
            "/api/contract-requests/",
            {
                "project": str(project.id),
                "description": "desc",
                "attachment": oversized_pdf_upload,
            },
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "attachment" in resp.json()

    def test_multiple_pending_requests_allowed(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        """Regression for 'account can only raise one request at a time'.
        The product rule is now: as long as a contract exists, the account
        can submit as many change requests as they want."""
        _create_contract_in_draft(project, subscriber_user)
        for i in range(3):
            resp = subscriber_client.post(
                "/api/contract-requests/",
                {"project": str(project.id), "description": f"Request {i}"},
                format="json",
            )
            assert resp.status_code == status.HTTP_201_CREATED
        from contracts.models import ContractRequest
        assert ContractRequest.objects.filter(project=project).count() == 3


# ─── Approve / reject ─────────────────────────────────────────────────────


class TestApproveReject:
    def _raise(self, subscriber_client, project):
        return subscriber_client.post(
            "/api/contract-requests/",
            {"project": str(project.id), "description": "change X"},
            format="json",
        ).json()

    def test_manager_approves_with_comment_auto_activates_contract(
        self,
        manager_client: APIClient,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        _create_contract_in_draft(project, subscriber_user)
        req = self._raise(subscriber_client, project)

        resp = manager_client.post(
            f"/api/contract-requests/{req['id']}/approve/",
            {"review_comment": "Looks good"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["status"] == "approved"
        assert body["review_comment"] == "Looks good"

        # Draft contract should auto-flip to active on approve
        from contracts.models import Contract
        contract = Contract.objects.get(project=project)
        assert contract.status == Contract.ACTIVE
        assert contract.activated_at is not None

    def test_manager_rejects_with_comment(
        self,
        manager_client: APIClient,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        _create_contract_in_draft(project, subscriber_user)
        req = self._raise(subscriber_client, project)

        resp = manager_client.post(
            f"/api/contract-requests/{req['id']}/reject/",
            {"review_comment": "Not aligned with policy"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["status"] == "rejected"
        assert body["review_comment"] == "Not aligned with policy"

    def test_reject_emits_notification(
        self,
        manager_client: APIClient,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        """Regression for the 'reject was silent' bug.

        Counts notifications created during the reject call. The raise
        also creates one, so we snapshot the count first and check the
        delta.
        """
        from notifications.models import Notification
        _create_contract_in_draft(project, subscriber_user)
        req = self._raise(subscriber_client, project)
        before = Notification.objects.count()

        manager_client.post(
            f"/api/contract-requests/{req['id']}/reject/",
            {"review_comment": "no"},
            format="json",
        )
        after = Notification.objects.count()
        assert after > before, "reject did not emit any notification"
        # And the new notification is specifically the rejected type.
        last = Notification.objects.order_by("-created_at").first()
        assert last.type == Notification.CONTRACT_REQUEST_REJECTED

    def test_account_cannot_approve(
        self,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        _create_contract_in_draft(project, subscriber_user)
        req = self._raise(subscriber_client, project)
        resp = subscriber_client.post(
            f"/api/contract-requests/{req['id']}/approve/", {}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_cannot_approve_already_reviewed_request(
        self,
        manager_client: APIClient,
        subscriber_client: APIClient,
        project,
        subscriber_user,
    ):
        _create_contract_in_draft(project, subscriber_user)
        req = self._raise(subscriber_client, project)
        manager_client.post(
            f"/api/contract-requests/{req['id']}/approve/",
            {"review_comment": "yes"},
            format="json",
        )
        # Second call should 400
        second = manager_client.post(
            f"/api/contract-requests/{req['id']}/approve/",
            {"review_comment": "again"},
            format="json",
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST

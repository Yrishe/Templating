from __future__ import annotations

import logging

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsInvitedAccount, IsManager
from projects.models import Project, ProjectMembership

from .models import EmailOrganiser, FinalResponse, IncomingEmail, InvitedAccount
from .serializers import (
    EmailOrganiserSerializer,
    FinalResponseSerializer,
    IncomingEmailSerializer,
    InvitedAccountSerializer,
)

logger = logging.getLogger(__name__)


def _require_project_membership(project_id, user) -> Project:
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise NotFound("Project not found.")
    if not ProjectMembership.objects.filter(project=project, user=user).exists():
        raise PermissionDenied("You are not a member of this project.")
    return project


class EmailOrganiserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EmailOrganiserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
        return organiser


class FinalResponseListCreateView(generics.ListCreateAPIView):
    serializer_class = FinalResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _get_organiser(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
        return organiser

    def get_queryset(self):
        organiser = self._get_organiser()
        return FinalResponse.objects.filter(email_organiser=organiser).prefetch_related("recipients")

    def perform_create(self, serializer):
        organiser = self._get_organiser()
        serializer.save(email_organiser=organiser)


class FinalResponseDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = FinalResponseSerializer
    permission_classes = [permissions.IsAuthenticated, IsInvitedAccount]

    def get_queryset(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        return FinalResponse.objects.filter(email_organiser__project=project).prefetch_related("recipients")

    def perform_update(self, serializer):
        # Record who edited
        try:
            invited = InvitedAccount.objects.get(
                project_id=self.kwargs["project_id"], user=self.request.user
            )
        except InvitedAccount.DoesNotExist:
            invited = None
        serializer.save(edited_by=invited)


class FinalResponseSendView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsInvitedAccount]

    def post(self, request: Request, project_id, pk) -> Response:
        _require_project_membership(project_id, request.user)
        try:
            fr = FinalResponse.objects.get(pk=pk, email_organiser__project_id=project_id)
        except FinalResponse.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if fr.status == FinalResponse.SENT:
            return Response({"detail": "Already sent."}, status=status.HTTP_400_BAD_REQUEST)
        from notifications.tasks import dispatch_final_response
        dispatch_final_response.delay(str(fr.pk))
        return Response({"detail": "Send queued."}, status=status.HTTP_202_ACCEPTED)


class ProjectInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsManager]

    def post(self, request: Request, project_id) -> Response:
        project = _require_project_membership(project_id, request.user)
        serializer = InvitedAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project, invited_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InvitedAccountListView(generics.ListAPIView):
    serializer_class = InvitedAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        return InvitedAccount.objects.filter(project=project).select_related("user", "invited_by")


# ─── Incoming email — listing & inbound webhook ──────────────────────────

class IncomingEmailListView(generics.ListAPIView):
    """List inbound emails routed to a project's mailbox."""

    serializer_class = IncomingEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        return IncomingEmail.objects.filter(project=project)


class InboundEmailWebhookView(APIView):
    """Webhook receiving parsed inbound emails from SES Inbound / SendGrid Inbound Parse / Postmark.

    Authentication is a shared secret in the `X-Webhook-Secret` header — set
    `INBOUND_EMAIL_WEBHOOK_SECRET` in the environment. For real SES Inbound,
    swap this for SNS signature verification.

    Expected JSON body (provider-agnostic):
    ```json
    {
      "from": "client@example.com",
      "from_name": "Acme Client",          // optional
      "to": "proj-12345678@inbound.contractmgr.app",
      "subject": "Re: Contract terms",
      "body_plain": "Plain text body...",
      "body_html": "<p>HTML body...</p>",  // optional
      "message_id": "<unique-id@mail.example.com>",
      "received_at": "2026-04-07T12:00:00Z"  // optional, defaults to now
    }
    ```
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request: Request) -> Response:
        # ── Shared-secret auth ────────────────────────────────────────────
        expected_secret = getattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", "") or ""
        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if not expected_secret or provided_secret != expected_secret:
            return Response({"detail": "Invalid webhook secret."}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}
        to_addr = (payload.get("to") or "").strip().lower()
        message_id = (payload.get("message_id") or "").strip()

        if not to_addr or not message_id:
            return Response(
                {"detail": "Missing required fields: 'to' and 'message_id'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Look up the project by its generic_email mailbox ──────────────
        try:
            project = Project.objects.get(generic_email__iexact=to_addr)
        except Project.DoesNotExist:
            logger.warning("InboundEmailWebhook: no project for to=%s", to_addr)
            return Response(
                {"detail": "No project matches this inbound address."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Idempotency: dedupe by message_id ─────────────────────────────
        if IncomingEmail.objects.filter(message_id=message_id).exists():
            return Response({"detail": "Duplicate message_id, ignored."}, status=status.HTTP_200_OK)

        received_at_raw = payload.get("received_at")
        received_at = parse_datetime(received_at_raw) if received_at_raw else None
        if received_at is None:
            received_at = timezone.now()

        incoming = IncomingEmail.objects.create(
            project=project,
            sender_email=(payload.get("from") or "").strip(),
            sender_name=(payload.get("from_name") or "").strip(),
            subject=(payload.get("subject") or "").strip(),
            body_plain=payload.get("body_plain") or "",
            body_html=payload.get("body_html") or "",
            message_id=message_id,
            received_at=received_at,
            raw_payload=payload,
        )

        # Fire the Claude suggestion task — best-effort (gracefully degrades
        # if the task module / Anthropic SDK is unavailable).
        try:
            from email_organiser.tasks import generate_suggested_reply
            generate_suggested_reply.delay(str(incoming.id))
        except Exception:
            logger.exception("InboundEmailWebhook: failed to enqueue suggested reply task")

        return Response(
            IncomingEmailSerializer(incoming).data,
            status=status.HTTP_201_CREATED,
        )

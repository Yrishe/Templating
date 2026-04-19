from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

MAX_RAW_PAYLOAD_BYTES = 256 * 1024  # 256 KB — see finding #11 in docs/security.md.

from accounts.permissions import IsInvitedAccount, IsManager
from projects.models import Project, ProjectMembership

from .models import EmailAnalysis, EmailOrganiser, IncomingEmail, InvitedAccount
from .serializers import (
    EmailAnalysisSerializer,
    EmailOrganiserSerializer,
    IncomingEmailSerializer,
    InvitedAccountSerializer,
)

logger = logging.getLogger(__name__)


def _require_project_membership(project_id, user) -> Project:
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        raise NotFound("Project not found.")
    if user.role != user.MANAGER and not ProjectMembership.objects.filter(
        project=project, user=user
    ).exists():
        raise PermissionDenied("You are not a member of this project.")
    return project


class EmailOrganiserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = EmailOrganiserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
        return organiser


# ─── Incoming email — listing, filtering, resolve, re-analyse ─────────

class IncomingEmailListView(generics.ListAPIView):
    """List inbound emails with classification data.

    Supports query params:
    - ?category=delay,costs  (comma-separated filter)
    - ?relevance=high,medium (comma-separated filter)
    - ?is_resolved=false
    - ?is_relevant=true
    """

    serializer_class = IncomingEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        qs = IncomingEmail.objects.filter(project=project).select_related("analysis")

        # Category filter
        categories = self.request.query_params.get("category")
        if categories:
            qs = qs.filter(category__in=categories.split(","))

        # Relevance filter
        relevances = self.request.query_params.get("relevance")
        if relevances:
            qs = qs.filter(relevance__in=relevances.split(","))

        # Resolved filter
        is_resolved = self.request.query_params.get("is_resolved")
        if is_resolved is not None:
            qs = qs.filter(is_resolved=is_resolved.lower() == "true")

        # Relevance flag filter
        is_relevant = self.request.query_params.get("is_relevant")
        if is_relevant is not None:
            qs = qs.filter(is_relevant=is_relevant.lower() == "true")

        return qs


class IncomingEmailDetailView(generics.RetrieveAPIView):
    """Get a single email with its full analysis."""

    serializer_class = IncomingEmailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = _require_project_membership(self.kwargs["project_id"], self.request.user)
        return IncomingEmail.objects.filter(project=project).select_related("analysis")


class IncomingEmailResolveView(APIView):
    """Mark an email occurrence as resolved."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, project_id, pk) -> Response:
        _require_project_membership(project_id, request.user)
        try:
            email = IncomingEmail.objects.get(pk=pk, project_id=project_id)
        except IncomingEmail.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        email.is_resolved = True
        email.save(update_fields=["is_resolved"])
        return Response(IncomingEmailSerializer(email).data)


class IncomingEmailReanalyseView(APIView):
    """Re-run the AI classification pipeline on an email."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, project_id, pk) -> Response:
        _require_project_membership(project_id, request.user)
        try:
            email = IncomingEmail.objects.get(pk=pk, project_id=project_id)
        except IncomingEmail.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Reset processing state
        email.is_processed = False
        email.save(update_fields=["is_processed"])

        # Delete existing analysis
        EmailAnalysis.objects.filter(email=email).delete()

        # Re-enqueue classification
        try:
            from email_organiser.tasks import classify_incoming_email
            classify_incoming_email.delay(str(email.pk))
        except Exception:
            logger.exception("IncomingEmailReanalyseView: failed to enqueue re-analysis")
            return Response(
                {"detail": "Failed to queue re-analysis."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"detail": "Re-analysis queued."}, status=status.HTTP_202_ACCEPTED)


class EmailAnalysisDetailView(generics.RetrieveAPIView):
    """Get the AI analysis for a specific email."""

    serializer_class = EmailAnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        _require_project_membership(self.kwargs["project_id"], self.request.user)
        try:
            return EmailAnalysis.objects.select_related("email").get(
                email_id=self.kwargs["pk"],
                email__project_id=self.kwargs["project_id"],
            )
        except EmailAnalysis.DoesNotExist:
            raise NotFound("Analysis not found for this email.")


# ─── Project invitations (unchanged) ─────────────────────────────────

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


# ─── Inbound webhook ─────────────────────────────────────────────────

class InboundEmailWebhookView(APIView):
    """Webhook receiving parsed inbound emails from SES / SendGrid / Postmark.

    After creating the IncomingEmail, fires the AI classification pipeline
    (classify → topic analysis → timeline generation) instead of the old
    reply-generation task.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "inbound_email"

    def post(self, request: Request) -> Response:
        expected_secret = getattr(settings, "INBOUND_EMAIL_WEBHOOK_SECRET", "") or ""
        provided_secret = request.headers.get("X-Webhook-Secret", "")
        if not expected_secret:
            logger.error("InboundEmailWebhook: INBOUND_EMAIL_WEBHOOK_SECRET is not configured")
            return Response({"detail": "Webhook not configured."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if not hmac.compare_digest(provided_secret, expected_secret):
            return Response({"detail": "Invalid webhook secret."}, status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data or {}
        to_addr = (payload.get("to") or "").strip().lower()
        message_id = (payload.get("message_id") or "").strip()

        if not to_addr or not message_id:
            return Response(
                {"detail": "Missing required fields: 'to' and 'message_id'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = Project.objects.get(generic_email__iexact=to_addr)
        except Project.DoesNotExist:
            logger.warning("InboundEmailWebhook: no project for to=%s", to_addr)
            return Response(
                {"detail": "No project matches this inbound address."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Idempotency
        if IncomingEmail.objects.filter(message_id=message_id).exists():
            return Response({"detail": "Duplicate message_id, ignored."}, status=status.HTTP_200_OK)

        received_at_raw = payload.get("received_at")
        received_at = parse_datetime(received_at_raw) if received_at_raw else None
        if received_at is None:
            received_at = timezone.now()

        # Cap the stored raw payload so a flood of large webhook calls can't
        # inflate DB storage. Parsed fields (subject, body, etc.) are kept
        # verbatim; only the JSONField copy is truncated.
        try:
            serialized = json.dumps(payload, default=str)
        except (TypeError, ValueError):
            serialized = ""
        if len(serialized) > MAX_RAW_PAYLOAD_BYTES:
            raw_payload_to_store: dict = {
                "_truncated": True,
                "size": len(serialized),
                "sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            }
        else:
            raw_payload_to_store = payload

        incoming = IncomingEmail.objects.create(
            project=project,
            sender_email=(payload.get("from") or "").strip(),
            sender_name=(payload.get("from_name") or "").strip(),
            subject=(payload.get("subject") or "").strip(),
            body_plain=payload.get("body_plain") or "",
            body_html=payload.get("body_html") or "",
            message_id=message_id,
            received_at=received_at,
            raw_payload=raw_payload_to_store,
        )

        # Notify project members of the new inbound email
        try:
            from notifications.tasks import create_incoming_email_notification
            create_incoming_email_notification.delay(str(incoming.id))
        except Exception:
            logger.exception("InboundEmailWebhook: failed to enqueue new-email notification")

        # Fire the AI classification pipeline
        try:
            from email_organiser.tasks import classify_incoming_email
            classify_incoming_email.delay(str(incoming.id))
        except Exception:
            logger.exception("InboundEmailWebhook: failed to enqueue classification pipeline")

        return Response(
            IncomingEmailSerializer(incoming).data,
            status=status.HTTP_201_CREATED,
        )

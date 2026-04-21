"""Dev helper — fire a synthetic inbound email at a project without HTTP.

Mirrors the code path of `InboundEmailWebhookView` (creates an IncomingEmail,
enqueues the notification task, enqueues the AI classification pipeline), but
skips the shared-secret header and rate-limiter that only make sense on the
HTTP surface. Use it to light up the classification + analysis + AI-thumbs
UI in dev without wiring a live mailbox into the webhook.

Examples:

    # Pick a project by generic_email address and send a delay-flavoured mail
    docker compose exec backend python manage.py simulate_inbound_email \\
        --project proj-alpha@test.com --subject "Delivery delay"

    # Or by project UUID, with a custom body + sender
    docker compose exec backend python manage.py simulate_inbound_email \\
        --project 2b6f4e... --subject "Cost overrun" \\
        --body-plain "We need a 12% budget increase for Q3." \\
        --from supplier@acme.example --from-name "Acme Supplier"
"""
from __future__ import annotations

import logging
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from email_organiser.models import IncomingEmail
from projects.models import Project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Simulate an inbound email hitting the webhook pipeline (dev only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            required=True,
            help="Project UUID or generic_email address to route the email to.",
        )
        parser.add_argument(
            "--subject",
            default="Simulated inbound email",
            help="Subject line. Default: 'Simulated inbound email'.",
        )
        parser.add_argument(
            "--body-plain",
            default=(
                "Hi,\n\nThis is a synthetic email produced by "
                "`manage.py simulate_inbound_email` for development. "
                "The AI classifier should pick it up and populate the "
                "email organiser UI.\n\nRegards,\nDev Harness"
            ),
            help="Plain-text body. Default: a generic dev message.",
        )
        parser.add_argument(
            "--body-html",
            default="",
            help="HTML body (optional).",
        )
        parser.add_argument(
            "--from",
            dest="from_email",
            default="dev-harness@example.com",
            help="Sender email. Default: dev-harness@example.com.",
        )
        parser.add_argument(
            "--from-name",
            default="Dev Harness",
            help="Sender display name.",
        )
        parser.add_argument(
            "--message-id",
            default=None,
            help="RFC-5322 Message-ID. Defaults to a fresh UUID-based value.",
        )
        parser.add_argument(
            "--skip-classify",
            action="store_true",
            help="Create the IncomingEmail row but don't enqueue the AI pipeline.",
        )

    def handle(self, *args, **options) -> None:
        project = self._resolve_project(options["project"])

        message_id = options["message_id"] or f"<sim-{uuid.uuid4()}@dev.local>"
        if IncomingEmail.objects.filter(message_id=message_id).exists():
            raise CommandError(
                f"message_id {message_id!r} already exists. Pass a different "
                f"--message-id or let the command generate one."
            )

        incoming = IncomingEmail.objects.create(
            project=project,
            sender_email=options["from_email"].strip(),
            sender_name=options["from_name"].strip(),
            subject=options["subject"].strip(),
            body_plain=options["body_plain"],
            body_html=options["body_html"],
            message_id=message_id,
            received_at=timezone.now(),
            raw_payload={"_source": "simulate_inbound_email"},
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created IncomingEmail {incoming.id} for project {project.id} "
            f"({project.generic_email or project.name})."
        ))

        # Same fan-out the real webhook does. Failures are logged but not fatal
        # — the row is already persisted, so a dev can re-run classification
        # via the re-analyse endpoint or restart the worker and `.delay()` again.
        try:
            from notifications.tasks import create_incoming_email_notification
            create_incoming_email_notification.delay(str(incoming.id))
            self.stdout.write("  → queued create_incoming_email_notification")
        except Exception:
            logger.exception("simulate_inbound_email: notification enqueue failed")
            self.stdout.write(self.style.WARNING("  → notification enqueue failed (see logs)"))

        if options["skip_classify"]:
            self.stdout.write("  → skipped classify_incoming_email (--skip-classify)")
            return

        try:
            from email_organiser.tasks import classify_incoming_email
            classify_incoming_email.delay(str(incoming.id))
            self.stdout.write("  → queued classify_incoming_email")
        except Exception:
            logger.exception("simulate_inbound_email: classification enqueue failed")
            self.stdout.write(self.style.WARNING("  → classification enqueue failed (see logs)"))

    def _resolve_project(self, needle: str) -> Project:
        needle = needle.strip()
        qs = Project.objects.filter(
            Q(generic_email__iexact=needle) | Q(pk=self._maybe_uuid(needle))
        )
        matches = list(qs[:2])
        if not matches:
            raise CommandError(
                f"No project matched {needle!r}. Pass either the generic_email "
                f"address or the project UUID."
            )
        if len(matches) > 1:
            raise CommandError(
                f"{needle!r} matched multiple projects — be more specific."
            )
        return matches[0]

    @staticmethod
    def _maybe_uuid(value: str):
        try:
            return uuid.UUID(value)
        except (ValueError, TypeError):
            # Return an impossible UUID so the Q() branch just doesn't match.
            return uuid.UUID(int=0)

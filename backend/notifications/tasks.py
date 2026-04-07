from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email(self, notification_id: str) -> None:
    """Fetch a notification, create an OutboundEmail record, and dispatch it."""
    from notifications.models import Notification, OutboundEmail

    try:
        notification = Notification.objects.select_related("project").get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.error("send_notification_email: notification %s not found", notification_id)
        return

    project = notification.project
    to_address = project.generic_email or ""
    if not to_address:
        logger.warning("send_notification_email: project %s has no generic_email", project.pk)
        return

    from_address = settings.DEFAULT_FROM_EMAIL
    subject = f"[{notification.get_type_display()}] Notification for {project.name}"
    body = (
        f"A new notification has been created for project '{project.name}'.\n"
        f"Type: {notification.get_type_display()}\n"
        f"Created at: {notification.created_at}\n"
    )

    outbound = OutboundEmail.objects.create(
        notification=notification,
        to_address=to_address,
        from_address=from_address,
        subject=subject,
        body=body,
        status=OutboundEmail.PENDING,
    )

    try:
        send_mail(subject, body, from_address, [to_address], fail_silently=False)
        outbound.status = OutboundEmail.SENT
        outbound.sent_at = timezone.now()
        outbound.save(update_fields=["status", "sent_at"])
    except Exception as exc:
        outbound.status = OutboundEmail.FAILED
        outbound.save(update_fields=["status"])
        logger.exception("send_notification_email: failed to send email for notification %s", notification_id)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def create_chat_message_notification(self, message_id: str) -> None:
    """Create a Notification when a new chat message is posted to a project."""
    from chat.models import Message
    from notifications.models import Notification

    try:
        message = Message.objects.select_related("chat__project").get(pk=message_id)
    except Message.DoesNotExist:
        logger.error("create_chat_message_notification: message %s not found", message_id)
        return

    Notification.objects.create(
        project=message.chat.project,
        type=Notification.CHAT_MESSAGE,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def create_contract_update_notification(self, contract_id: str, action: str = "updated") -> None:
    """Create a Notification when a project's contract is created/updated/activated.

    `action` is currently informational only — kept on the signature so callers can
    distinguish create vs update vs activate when richer notification copy is added.
    """
    from contracts.models import Contract
    from notifications.models import Notification

    try:
        contract = Contract.objects.select_related("project").get(pk=contract_id)
    except Contract.DoesNotExist:
        logger.error("create_contract_update_notification: contract %s not found", contract_id)
        return

    Notification.objects.create(
        project=contract.project,
        type=Notification.CONTRACT_UPDATE,
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def create_contract_request_notification(self, contract_request_id: str) -> None:
    """Create a Notification triggered by a ContractRequest status change."""
    from contracts.models import ContractRequest
    from notifications.models import Notification

    try:
        cr = ContractRequest.objects.select_related("project").get(pk=contract_request_id)
    except ContractRequest.DoesNotExist:
        logger.error("create_contract_request_notification: contract request %s not found", contract_request_id)
        return

    notification = Notification.objects.create(
        project=cr.project,
        type=Notification.CONTRACT_REQUEST,
        triggered_by_contract_request=cr,
    )

    # Queue the email dispatch
    send_notification_email.delay(str(notification.pk))


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_final_response(self, final_response_id: str) -> None:
    """Send a FinalResponse to all its recipients via email."""
    from django.utils import timezone as tz

    from email_organiser.models import FinalResponse

    try:
        final_response = FinalResponse.objects.prefetch_related("recipients").select_related(
            "email_organiser__project"
        ).get(pk=final_response_id)
    except FinalResponse.DoesNotExist:
        logger.error("dispatch_final_response: final_response %s not found", final_response_id)
        return

    from_address = settings.DEFAULT_FROM_EMAIL
    recipients = list(final_response.recipients.all())
    if not recipients:
        logger.warning("dispatch_final_response: no recipients for final_response %s", final_response_id)
        return

    to_addresses = [r.email for r in recipients]

    try:
        send_mail(
            subject=final_response.subject,
            message=final_response.content,
            from_email=from_address,
            recipient_list=to_addresses,
            fail_silently=False,
        )
        final_response.status = FinalResponse.SENT
        final_response.sent_at = tz.now()
        final_response.save(update_fields=["status", "sent_at"])
        logger.info("dispatch_final_response: sent final_response %s to %s", final_response_id, to_addresses)
    except Exception as exc:
        logger.exception("dispatch_final_response: failed to send final_response %s", final_response_id)
        raise self.retry(exc=exc)

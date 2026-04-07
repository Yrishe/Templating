"""Background tasks for the email_organiser app.

Phase 3 item 10: when a new IncomingEmail is created (by the inbound webhook),
we ask Claude to draft a reply that is **grounded in the project's contract**
text. The contract text comes from `contracts.tasks.extract_contract_text`
(Phase 3 item 9), which runs whenever a contract PDF is uploaded.

The narrowed-knowledge approach: instead of giving Claude generic instructions
or a vector index, we pass ONLY the contract for this specific project as
system context. This keeps responses tightly scoped and dramatically improves
accuracy for contract-related questions.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """\
You are a contract management assistant helping to draft a professional reply to an inbound email.

Use ONLY the contract text below as your source of truth. If the answer to a
question is not in the contract, say so explicitly rather than inventing terms.
Stay concise, professional, and reference specific clauses where relevant.

CONTRACT TITLE: {contract_title}

CONTRACT TEXT:
\"\"\"
{contract_text}
\"\"\"
"""

USER_PROMPT_TEMPLATE = """\
Please draft a reply to the following email. Return only the reply body text
(no subject line, no salutation/sign-off boilerplate unless contextually
appropriate).

FROM: {sender_name} <{sender_email}>
SUBJECT: {subject}

BODY:
{body}
"""


def _build_placeholder_reply(incoming) -> str:
    """Returned when the Anthropic SDK or API key is unavailable."""
    return (
        f"[AI suggestion unavailable — please draft a reply manually.]\n\n"
        f"Original message from {incoming.sender_email}:\n"
        f"Subject: {incoming.subject}\n\n"
        f"{incoming.body_plain[:500]}"
    )


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_suggested_reply(self, incoming_email_id: str) -> None:
    """Generate a Claude-drafted reply for an inbound email and save it as a
    `FinalResponse` (status='suggested', is_ai_generated=True).
    """
    from email_organiser.models import EmailOrganiser, FinalResponse, IncomingEmail

    try:
        incoming = IncomingEmail.objects.select_related("project").get(pk=incoming_email_id)
    except IncomingEmail.DoesNotExist:
        logger.error("generate_suggested_reply: incoming email %s not found", incoming_email_id)
        return

    project = incoming.project

    # ── Pull the contract context (narrowed knowledge) ────────────────────
    contract_text = ""
    contract_title = "(no contract uploaded)"
    try:
        contract = project.contract  # OneToOne related_name on Contract
        contract_text = contract.content or ""
        contract_title = contract.title
    except Exception:
        logger.info(
            "generate_suggested_reply: project %s has no contract yet — Claude "
            "will be told the contract is unavailable.",
            project.pk,
        )

    if not contract_text:
        contract_text = "(Contract text has not been extracted yet — answer based on general professional standards and flag this clearly to the user.)"

    # ── Call Claude (gracefully degrades if SDK / key unavailable) ────────
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")

    suggestion_text: str
    if not api_key:
        logger.warning(
            "generate_suggested_reply: ANTHROPIC_API_KEY not set — creating a "
            "placeholder draft instead of calling Claude."
        )
        suggestion_text = _build_placeholder_reply(incoming)
    else:
        try:
            from anthropic import Anthropic
        except ImportError:
            logger.warning(
                "generate_suggested_reply: anthropic SDK not installed — install "
                "it with `pip install anthropic`. Falling back to placeholder."
            )
            suggestion_text = _build_placeholder_reply(incoming)
        else:
            try:
                client = Anthropic(api_key=api_key)
                response = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT_TEMPLATE.format(
                        contract_title=contract_title,
                        contract_text=contract_text[:50_000],  # cap context size
                    ),
                    messages=[
                        {
                            "role": "user",
                            "content": USER_PROMPT_TEMPLATE.format(
                                sender_name=incoming.sender_name or "",
                                sender_email=incoming.sender_email,
                                subject=incoming.subject,
                                body=incoming.body_plain[:20_000],
                            ),
                        }
                    ],
                )
                # The SDK returns a list of content blocks; concatenate text blocks.
                parts: list[str] = []
                for block in response.content:
                    text = getattr(block, "text", None)
                    if text:
                        parts.append(text)
                suggestion_text = "\n".join(parts).strip() or _build_placeholder_reply(incoming)
            except Exception as exc:
                logger.exception(
                    "generate_suggested_reply: Claude API call failed for %s",
                    incoming_email_id,
                )
                # Retry transient failures
                try:
                    raise self.retry(exc=exc)
                except self.MaxRetriesExceededError:
                    suggestion_text = _build_placeholder_reply(incoming)

    # ── Persist as a draft FinalResponse linked to the inbound email ──────
    organiser, _ = EmailOrganiser.objects.get_or_create(project=project)
    subject = incoming.subject
    if subject and not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    FinalResponse.objects.create(
        email_organiser=organiser,
        source_incoming_email=incoming,
        subject=subject or "Re: (no subject)",
        content=suggestion_text,
        status=FinalResponse.SUGGESTED,
        is_ai_generated=True,
    )

    incoming.is_processed = True
    incoming.save(update_fields=["is_processed"])

    logger.info(
        "generate_suggested_reply: created suggested FinalResponse for incoming %s",
        incoming_email_id,
    )

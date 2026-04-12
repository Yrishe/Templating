"""Background tasks for the email_organiser app.

AI Email Triage Pipeline
========================
When a new IncomingEmail arrives, the pipeline runs three stages:

1. **Classifier Agent** — scans for keywords, determines relevance (high/medium/
   low/none) and assigns a category (delay, damage, costs, scope_change, etc.).
   Irrelevant emails are flagged and excluded from further analysis.

2. **Specialized Topic Agent** — a separate prompt tailored to the email's
   category (costs agent, delay agent, scope agent, …). Each agent analyses the
   email against the project's contract to assess risk, suggest mitigation,
   recommend a response, and outline a resolution path. Splitting by topic
   avoids hallucination by keeping each agent narrowly focused.

3. **Timeline Generator Agent** — if the email is relevant, creates a
   TimelineEvent on the project's timeline with an appropriate label, priority,
   and description of how the occurrence impacts the schedule.

After the pipeline completes, notifications are fired for high-relevance emails
so the project's notification panel surfaces urgent occurrences.
"""

from __future__ import annotations

import json
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Agent system prompts — one per concern to avoid cross-contamination
# ═══════════════════════════════════════════════════════════════════════

CLASSIFIER_SYSTEM_PROMPT = """\
You are an email classification agent for a contract management platform.

Your ONLY job is to read the email below and return a JSON object with:
- "is_relevant": boolean — is this email relevant to the project/contract?
- "relevance": "high" | "medium" | "low" | "none"
- "category": one of "delay", "damage", "scope_change", "costs", "delivery", "compliance", "quality", "dispute", "general", "irrelevant"
- "keywords": list of up to 10 key terms extracted from the email

Rules:
- Emails about delays, damages, cost changes, scope changes, delivery issues, compliance, quality problems, or disputes are RELEVANT.
- Marketing, spam, newsletters, or unrelated correspondence is IRRELEVANT.
- When in doubt, classify as "general" with "medium" relevance.
- Return ONLY valid JSON. No explanation, no markdown.
"""

CLASSIFIER_USER_TEMPLATE = """\
FROM: {sender_name} <{sender_email}>
SUBJECT: {subject}

BODY:
{body}
"""


def _topic_system_prompt(topic: str, contract_title: str, contract_text: str) -> str:
    """Build a system prompt for a specialized topic agent."""
    topic_instructions = {
        "costs": (
            "You are a COSTS specialist agent. Focus exclusively on financial "
            "implications: budget overruns, price escalations, payment disputes, "
            "penalties, and cost-related contract clauses."
        ),
        "delay": (
            "You are a DELAY specialist agent. Focus exclusively on timeline "
            "slippages: schedule delays, missed milestones, force majeure claims, "
            "extension requests, and delay-related contract clauses."
        ),
        "scope_change": (
            "You are a SCOPE CHANGE specialist agent. Focus exclusively on scope "
            "modifications: change orders, additional work requests, scope creep, "
            "variation notices, and scope-related contract clauses."
        ),
        "damage": (
            "You are a DAMAGE specialist agent. Focus exclusively on damage "
            "reports: property damage, defects, insurance claims, liability, "
            "and damage-related contract clauses."
        ),
        "delivery": (
            "You are a DELIVERY specialist agent. Focus exclusively on delivery "
            "matters: shipment issues, acceptance criteria, handover processes, "
            "delivery milestones, and delivery-related contract clauses."
        ),
        "compliance": (
            "You are a COMPLIANCE specialist agent. Focus exclusively on "
            "regulatory and contractual compliance: legal requirements, permit "
            "issues, standards violations, and compliance-related clauses."
        ),
        "quality": (
            "You are a QUALITY specialist agent. Focus exclusively on quality "
            "issues: defects, inspections, non-conformance, rework requirements, "
            "and quality-related contract clauses."
        ),
        "dispute": (
            "You are a DISPUTE specialist agent. Focus exclusively on conflict "
            "matters: claims, disagreements, mediation, arbitration, and "
            "dispute-resolution contract clauses."
        ),
    }

    agent_role = topic_instructions.get(topic, (
        "You are a GENERAL analysis agent. Assess the email for any contract-"
        "relevant concerns."
    ))

    return f"""\
{agent_role}

Analyse the email below STRICTLY against the project's contract.
The contract is your ONLY source of truth. If the contract does not cover a
topic, say so explicitly — never invent terms or clauses.

Return a JSON object with these fields:
- "risk_level": "low" | "medium" | "high" | "critical"
- "risk_summary": A 2-3 sentence summary of the risk this email represents.
- "contract_references": Relevant clauses or sections of the contract that apply (quote briefly).
- "mitigation": Concrete steps to mitigate the situation, referencing the contract.
- "suggested_response": How the project team should respond to the sender.
- "resolution_path": Step-by-step path to resolve the situation.
- "timeline_impact": How this will affect the project timeline (or "none" if no impact).

Return ONLY valid JSON. No explanation, no markdown fences.

CONTRACT TITLE: {contract_title}

CONTRACT TEXT:
\"\"\"
{contract_text}
\"\"\"
"""


TIMELINE_SYSTEM_PROMPT = """\
You are a timeline task generator for a contract management platform.

Based on the email analysis below, generate a JSON object describing a new
timeline event to add to the project's timeline:
- "title": short (max 80 chars) task title describing the occurrence
- "description": 2-4 sentences explaining the occurrence, its impact on the timeline, and key information from the email
- "priority": "low" | "medium" | "high" | "critical"
- "deadline_days": integer — suggested number of days from today to set as deadline (based on urgency)

Rules:
- The title should be actionable (e.g. "Review cost escalation claim", "Address delivery delay from Supplier X")
- Include the category topic as context (e.g. costs, delay, scope)
- Be specific about the impact on the project schedule
- Return ONLY valid JSON. No explanation, no markdown.
"""


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 1024) -> str | None:
    """Call the Anthropic API. Returns the text response or None on failure."""
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "") or ""
    model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")

    if not api_key:
        logger.warning("_call_claude: ANTHROPIC_API_KEY not set")
        return None

    try:
        from anthropic import Anthropic
    except ImportError:
        logger.warning("_call_claude: anthropic SDK not installed")
        return None

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts).strip() or None
    except Exception:
        logger.exception("_call_claude: API call failed")
        return None


def _parse_json(text: str | None) -> dict | None:
    """Attempt to parse a JSON string, stripping markdown fences if present."""
    if not text:
        return None
    # Strip markdown code fences that models sometimes add
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_parse_json: failed to parse: %s", text[:200])
        return None


# ═══════════════════════════════════════════════════════════════════════
# Stage 1: Classifier Agent
# ═══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def classify_incoming_email(self, incoming_email_id: str) -> None:
    """Stage 1 — classify an incoming email for relevance and category.

    On success, chains into the appropriate specialized topic agent (stage 2).
    Irrelevant emails are marked and no further processing occurs.
    """
    from email_organiser.models import IncomingEmail

    try:
        incoming = IncomingEmail.objects.select_related("project").get(pk=incoming_email_id)
    except IncomingEmail.DoesNotExist:
        logger.error("classify_incoming_email: email %s not found", incoming_email_id)
        return

    user_message = CLASSIFIER_USER_TEMPLATE.format(
        sender_name=incoming.sender_name or "",
        sender_email=incoming.sender_email,
        subject=incoming.subject,
        body=incoming.body_plain[:20_000],
    )

    result_text = _call_claude(CLASSIFIER_SYSTEM_PROMPT, user_message, max_tokens=512)
    result = _parse_json(result_text)

    if result is None:
        # Fallback: treat as general/medium so we don't lose emails
        logger.warning(
            "classify_incoming_email: AI classification failed for %s — using defaults",
            incoming_email_id,
        )
        result = {
            "is_relevant": True,
            "relevance": "medium",
            "category": "general",
            "keywords": [],
        }

    # Persist classification
    valid_relevances = {c[0] for c in IncomingEmail.RELEVANCE_CHOICES}
    valid_categories = {c[0] for c in IncomingEmail.CATEGORY_CHOICES}

    relevance = result.get("relevance", "medium")
    if relevance not in valid_relevances:
        relevance = "medium"

    category = result.get("category", "general")
    if category not in valid_categories:
        category = "general"

    is_relevant = result.get("is_relevant", True)
    if not is_relevant:
        relevance = "none"
        category = "irrelevant"

    keywords = result.get("keywords", [])
    if isinstance(keywords, list):
        keywords = ", ".join(str(k) for k in keywords[:10])
    else:
        keywords = str(keywords)[:500]

    incoming.is_relevant = is_relevant
    incoming.relevance = relevance
    incoming.category = category
    incoming.keywords = keywords
    incoming.save(update_fields=["is_relevant", "relevance", "category", "keywords"])

    if not is_relevant:
        # Irrelevant — mark processed, do not continue pipeline
        incoming.is_processed = True
        incoming.save(update_fields=["is_processed"])
        logger.info("classify_incoming_email: email %s classified as irrelevant", incoming_email_id)
        return

    # Chain to stage 2: specialized topic analysis
    try:
        analyse_email_by_topic.delay(incoming_email_id)
    except Exception:
        logger.exception("classify_incoming_email: failed to enqueue topic analysis")


# ═══════════════════════════════════════════════════════════════════════
# Stage 2: Specialized Topic Agent
# ═══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analyse_email_by_topic(self, incoming_email_id: str) -> None:
    """Stage 2 — run the specialized topic agent for the email's category.

    Uses the project's contract as the reference for all decisions.
    On success, chains into the timeline generator (stage 3).
    """
    from email_organiser.models import EmailAnalysis, IncomingEmail

    try:
        incoming = IncomingEmail.objects.select_related("project").get(pk=incoming_email_id)
    except IncomingEmail.DoesNotExist:
        logger.error("analyse_email_by_topic: email %s not found", incoming_email_id)
        return

    project = incoming.project

    # Pull contract context
    contract_text = ""
    contract_title = "(no contract uploaded)"
    try:
        contract = project.contract
        contract_text = contract.content or ""
        contract_title = contract.title
    except Exception:
        pass

    if not contract_text:
        contract_text = (
            "(Contract text has not been extracted yet — analyse based on "
            "general professional standards and flag this clearly.)"
        )

    topic = incoming.category
    system_prompt = _topic_system_prompt(
        topic, contract_title, contract_text[:50_000]
    )

    user_message = (
        f"FROM: {incoming.sender_name or ''} <{incoming.sender_email}>\n"
        f"SUBJECT: {incoming.subject}\n"
        f"CATEGORY: {topic}\n"
        f"RELEVANCE: {incoming.relevance}\n"
        f"KEYWORDS: {incoming.keywords}\n\n"
        f"BODY:\n{incoming.body_plain[:20_000]}"
    )

    result_text = _call_claude(system_prompt, user_message, max_tokens=2048)
    result = _parse_json(result_text)

    if result is None:
        logger.warning(
            "analyse_email_by_topic: topic analysis failed for %s — storing defaults",
            incoming_email_id,
        )
        result = {
            "risk_level": "medium",
            "risk_summary": "AI analysis unavailable — manual review required.",
            "contract_references": "",
            "mitigation": "",
            "suggested_response": "",
            "resolution_path": "",
            "timeline_impact": "",
        }

    valid_risk_levels = {"low", "medium", "high", "critical"}
    risk_level = result.get("risk_level", "medium")
    if risk_level not in valid_risk_levels:
        risk_level = "medium"

    # Upsert analysis (OneToOne on email)
    EmailAnalysis.objects.update_or_create(
        email=incoming,
        defaults={
            "agent_topic": topic,
            "risk_level": risk_level,
            "risk_summary": result.get("risk_summary", "")[:2000],
            "contract_references": result.get("contract_references", "")[:2000],
            "mitigation": result.get("mitigation", "")[:2000],
            "suggested_response": result.get("suggested_response", "")[:2000],
            "resolution_path": result.get("resolution_path", "")[:2000],
            "timeline_impact": result.get("timeline_impact", "")[:2000],
        },
    )

    # Chain to stage 3: timeline event generation
    try:
        generate_timeline_event_from_email.delay(incoming_email_id)
    except Exception:
        logger.exception("analyse_email_by_topic: failed to enqueue timeline generation")

    # Fire notification for high-relevance emails
    if incoming.relevance == IncomingEmail.RELEVANCE_HIGH:
        try:
            from notifications.tasks import create_email_occurrence_notification
            create_email_occurrence_notification.delay(incoming_email_id)
        except Exception:
            logger.exception("analyse_email_by_topic: failed to enqueue notification")


# ═══════════════════════════════════════════════════════════════════════
# Stage 3: Timeline Generator Agent
# ═══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_timeline_event_from_email(self, incoming_email_id: str) -> None:
    """Stage 3 — generate a timeline event from a classified & analysed email.

    Creates a TimelineEvent on the project's timeline labelled with the email's
    category and containing key information about the occurrence.
    """
    from datetime import timedelta

    from django.utils import timezone

    from email_organiser.models import EmailAnalysis, IncomingEmail
    from projects.models import Timeline, TimelineEvent

    try:
        incoming = IncomingEmail.objects.select_related("project").get(pk=incoming_email_id)
    except IncomingEmail.DoesNotExist:
        logger.error("generate_timeline_event_from_email: email %s not found", incoming_email_id)
        return

    # Get the analysis
    try:
        analysis = EmailAnalysis.objects.get(email=incoming)
    except EmailAnalysis.DoesNotExist:
        logger.error(
            "generate_timeline_event_from_email: no analysis for email %s", incoming_email_id
        )
        incoming.is_processed = True
        incoming.save(update_fields=["is_processed"])
        return

    # Category label for the title
    category_labels = dict(IncomingEmail.CATEGORY_CHOICES)
    category_label = category_labels.get(incoming.category, "General")

    # Build the user prompt for the timeline agent
    user_message = (
        f"CATEGORY: {category_label}\n"
        f"EMAIL SUBJECT: {incoming.subject}\n"
        f"FROM: {incoming.sender_name or incoming.sender_email}\n"
        f"RELEVANCE: {incoming.relevance}\n"
        f"RISK LEVEL: {analysis.risk_level}\n"
        f"RISK SUMMARY: {analysis.risk_summary}\n"
        f"TIMELINE IMPACT: {analysis.timeline_impact}\n"
        f"MITIGATION: {analysis.mitigation}\n"
    )

    result_text = _call_claude(TIMELINE_SYSTEM_PROMPT, user_message, max_tokens=512)
    result = _parse_json(result_text)

    today = timezone.now().date()

    if result is None:
        # Fallback: create a generic event
        result = {
            "title": f"[{category_label}] {incoming.subject[:60]}",
            "description": (
                f"Auto-generated from email by {incoming.sender_name or incoming.sender_email}.\n"
                f"Risk: {analysis.risk_level}. {analysis.risk_summary[:200]}"
            ),
            "priority": analysis.risk_level,
            "deadline_days": 7,
        }

    # Map risk/priority
    priority = result.get("priority", "medium")
    if priority not in {"low", "medium", "high", "critical"}:
        priority = "medium"

    deadline_days = result.get("deadline_days", 7)
    try:
        deadline_days = max(1, min(90, int(deadline_days)))
    except (ValueError, TypeError):
        deadline_days = 7

    # Create the timeline event
    timeline, _ = Timeline.objects.get_or_create(project=incoming.project)
    event = TimelineEvent.objects.create(
        timeline=timeline,
        title=str(result.get("title", f"[{category_label}] Review required"))[:255],
        description=str(result.get("description", ""))[:2000],
        start_date=today,
        end_date=today + timedelta(days=deadline_days),
        status=TimelineEvent.PLANNED,
        priority=priority,
        deadline_reminder_days=min(deadline_days, 3),
    )

    # Link analysis to the generated event
    analysis.generated_timeline_event = event
    analysis.save(update_fields=["generated_timeline_event"])

    # Mark email as fully processed
    incoming.is_processed = True
    incoming.save(update_fields=["is_processed"])

    logger.info(
        "generate_timeline_event_from_email: created event '%s' for email %s",
        event.title,
        incoming_email_id,
    )


# ═══════════════════════════════════════════════════════════════════════
# Legacy: kept for backward compatibility (existing webhook calls this)
# ═══════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def generate_suggested_reply(self, incoming_email_id: str) -> None:
    """Legacy — now redirects to the new classification pipeline."""
    classify_incoming_email.delay(incoming_email_id)

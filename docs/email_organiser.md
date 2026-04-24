# Email Organiser

AI-assisted inbound email triage for the contract-management product. When a project-addressed email lands, the system classifies it, analyses it against the project's contract, and (for relevant emails) generates a timeline event and a suggested reply.

Source: [backend/email_organiser/](../backend/email_organiser/). Frontend: [email-organiser/](../frontend/src/app/\(app\)/email-organiser/). High-level diagram: [EmailOrganiser.drawio](../EmailOrganiser.drawio).

## What it does

1. An inbound email provider (Brevo in our deploy, Postmark / SendGrid / SES Inbound equivalent elsewhere) parses a message sent to `<project-slug>@<inbound-domain>` and POSTs a JSON payload to our webhook.
2. The webhook validates the HMAC secret, dedupes on `message_id`, and persists an `IncomingEmail` row.
3. A Celery chain runs four stages: **classify → analyse by topic → generate timeline event → generate suggested reply**. Each stage is a separate task, chained by `delay()` after the previous completes.
4. Project members see the result on `/email-organiser/<projectId>`: a list of classified emails with relevance + category badges, and a side panel showing the AI analysis for the selected email.
5. Managers' feedback on each AI output (classification + suggestion) flows back via `<AiFeedback>` 👍/👎, building a labelled evaluation dataset for future model changes.

## Data model

Four models in [email_organiser/models.py](../backend/email_organiser/models.py):

| Model | Purpose |
|---|---|
| `EmailOrganiser` | One per project (auto-created). Holds per-project AI context — currently just `ai_context` free text. |
| `IncomingEmail` | Every parsed webhook payload becomes one of these. Deduped by `message_id` (RFC 5322). Holds sender, subject, body, raw payload (capped at 256 KB), classification outputs (`is_relevant`, `relevance`, `category`, `keywords`), and resolution state (`is_resolved`). |
| `EmailAnalysis` | OneToOne with `IncomingEmail`. Holds the specialized topic agent's output: `risk_level`, `risk_summary`, `contract_references`, `mitigation`, `suggested_response`, `resolution_path`, `timeline_impact`, and an optional FK to an auto-generated `TimelineEvent`. |
| `InvitedAccount` | Legacy. One per invited user per project. The primary invite flow now uses `ProjectMembership`; this model is mirrored during `ProjectInviteView.post` for backward compatibility. |

**Relevance levels:** `high` · `medium` · `low` · `none` (irrelevant, excluded from base knowledge).

**Categories:** `delay` · `damage` · `scope_change` · `costs` · `delivery` · `compliance` · `quality` · `dispute` · `general` · `irrelevant`.

**Indexes:** `(project)`, `(received_at)`, `(category)`, `(relevance)`, `(is_resolved)` — all on `IncomingEmail`, sized for the UI's filter-heavy list view.

## The pipeline

All four stages live in [email_organiser/tasks.py](../backend/email_organiser/tasks.py) as `@shared_task(bind=True, max_retries=2, default_retry_delay=60)` Celery tasks.

```
Inbound HTTP ─▶ InboundEmailWebhookView
                │
                ├─▶ classify_incoming_email.delay()          (Stage 1)
                │   │
                │   ├─ is_relevant=False → stop (is_processed=True)
                │   └─ is_relevant=True  → analyse_email_by_topic.delay()   (Stage 2)
                │                           │
                │                           ├─▶ generate_timeline_event_from_email.delay()  (Stage 3)
                │                           └─▶ generate_suggested_reply.delay()            (Stage 4)
                │
                └─▶ create_incoming_email_notification.delay()  (notifications/tasks.py)
```

### Stage 0 — Inbound webhook

[`InboundEmailWebhookView.post`](../backend/email_organiser/views.py) — mounted at `POST /api/webhooks/inbound-email/`.

- `permission_classes = [AllowAny]`, `authentication_classes = []` — no JWT needed; the HMAC-ish header is the entire auth.
- Required header: `X-Webhook-Secret` matching `settings.INBOUND_EMAIL_WEBHOOK_SECRET`. Compared with `hmac.compare_digest`. Missing secret on the server → 503 (not 401) so misconfiguration is obvious.
- Required payload fields: `to` (project's `generic_email`) and `message_id`. Missing → 400.
- Idempotency: if an `IncomingEmail` with this `message_id` already exists → 200 with `{"detail": "Duplicate, ignored."}`. Critical for webhook retries from the upstream provider.
- Payload cap: if `json.dumps(payload)` exceeds 256 KB, the stored `raw_payload` is replaced with `{"_truncated": True, "size": N, "sha256": ...}`. Parsed fields (subject, body, sender) are kept verbatim.
- Rate limit: `ScopedRateThrottle` with scope `inbound_email` (60/min). Scoped to the webhook endpoint only so a misbehaving provider can't drown legit traffic.

On success: creates the `IncomingEmail` row, fires `create_incoming_email_notification.delay()` for member notifications, fires `classify_incoming_email.delay()` to start the AI pipeline. Returns 201 with the serialized email.

### Stage 1 — Classifier agent

[`classify_incoming_email`](../backend/email_organiser/tasks.py) · prompt at `CLASSIFIER_SYSTEM_PROMPT` (lines 40-54).

Prompt scope is deliberately narrow — one job: return a 4-field JSON (`is_relevant`, `relevance`, `category`, `keywords`). Max 512 tokens. No contract context at this stage; relevance + category only.

Post-processing ([tasks.py:258-285](../backend/email_organiser/tasks.py#L258)):
- Validates `relevance` and `category` against the model's choice tuples; unknown values fall back to `medium` / `general`.
- `is_relevant=False` forces `relevance=none, category=irrelevant` to keep the UI's filters coherent.
- `keywords` is normalised to a comma-joined string, first 10 entries only.
- **On AI failure** (API unreachable, malformed JSON, 429) — falls back to `{is_relevant: True, relevance: medium, category: general}` so emails are never silently lost.

Writes back only four fields: `is_relevant`, `relevance`, `category`, `keywords`.

Chains to Stage 2 only when `is_relevant=True`. Irrelevant emails are marked `is_processed=True` and the pipeline stops.

### Stage 2 — Specialized topic agent

[`analyse_email_by_topic`](../backend/email_organiser/tasks.py#L305) · prompt factory at `_topic_system_prompt()` (lines 65-139).

One prompt per category. A `costs` agent ignores delays; a `delay` agent ignores damages. This narrow-focus design is the main anti-hallucination lever — the contract text is 20+ KB and a generalist prompt routinely mis-assigns clauses. Eight specialized prompts plus a `general` fallback.

The contract is the **only** source of truth the prompt accepts. The instruction block says explicitly: _"If the contract does not cover a topic, say so explicitly — never invent terms or clauses."_

Max 2048 tokens (wider than classification — the output is five prose fields). Output: one JSON object with `risk_level`, `risk_summary`, `contract_references`, `mitigation`, `suggested_response`, `resolution_path`, `timeline_impact`.

Failure behaviour:
- Contract text missing → prompt receives `"(Contract text has not been extracted yet — analyse based on general professional standards and flag this clearly.)"` as a degraded fallback. The agent self-flags its lower confidence.
- AI returns non-JSON → row still created with best-effort parsing; missing fields default to empty strings.

Chains to Stage 3 (timeline generator) and Stage 4 (suggested reply) when the analysis row persists.

### Stage 3 — Timeline event generator

[`generate_timeline_event_from_email`](../backend/email_organiser/tasks.py#L409) · prompt at `TIMELINE_SYSTEM_PROMPT` (lines 142-157).

Takes the email + its analysis as context. Generates `{title, description, priority, deadline_days}`. Creates a `TimelineEvent` on the project's timeline with `created_by=None` (it's AI, no human actor) and attaches the FK back to `EmailAnalysis.generated_timeline_event` so the UI can deep-link.

Failure mode: returns silently on bad JSON; no event is created, `EmailAnalysis.generated_timeline_event` stays null.

### Stage 4 — Suggested reply generator

[`generate_suggested_reply`](../backend/email_organiser/tasks.py#L516). Creates a `FinalResponse` row in `status=suggested` ready for the user to review, edit, and send. Currently the UI doesn't expose the "send" action (no SMTP outbound wiring to inbound-parse replies yet) — the draft surface exists as a primitive for the next phase.

## Frontend surface

Route: `/email-organiser/<projectId>`. Two-panel layout:

- **List** ([EmailOrganiserPanel](../frontend/src/components/email-organiser/email-organiser-panel.tsx)) — filterable grid of incoming emails with relevance + category badges. Filters: `?category=delay,costs`, `?relevance=high,medium`, `?is_resolved=false`, `?is_relevant=true`.
- **Analysis panel** ([AnalysisPanel](../frontend/src/components/email-organiser/analysis-panel.tsx)) — detail view for the selected email. Shows the analysis's six prose fields, the auto-generated timeline event deep-link (if any), and the AI thumbs widget. Actions: **Resolve** (marks `is_resolved=true`), **Re-analyse** (clears state + re-enqueues the pipeline).

Inline `<AiFeedback>` widgets on both the classification row and the suggested-reply block capture 👍/👎 + an optional reason. That feeds the labelled evaluation dataset described in [docs/research.md §A.1](research.md#a1-ai-suggestion-thumbs).

Hook: [useEmailOrganiser](../frontend/src/hooks/use-email-organiser.ts) for incoming-email list/detail/resolve/reanalyse.

## Dev harness

No live mailbox? No problem. Ship a fake email into the pipeline with:

```bash
docker compose exec backend python manage.py simulate_inbound_email \
  --project website-project@smithconsulting.com \
  --subject "Delay on phase 2 delivery" \
  --body-plain "Vendor says scaffolding lead time doubled; requesting a 10-day extension."
```

Flags:

| Flag | Purpose |
|---|---|
| `--project <uuid_or_email>` | Resolve by UUID or `generic_email`. Required. |
| `--subject <s>` | Default: "Simulated inbound email". |
| `--body-plain <s>` | Default: a generic dev message. |
| `--body-html <s>` | Optional. |
| `--from <email>` / `--from-name <name>` | Default: `dev-harness@example.com` / `Dev Harness`. |
| `--message-id <id>` | Default: `<sim-{uuid}@dev.local>`. Collision → CommandError (use a fresh one or let it generate). |
| `--skip-classify` | Create the row but don't enqueue the AI pipeline — useful when you don't want to burn Anthropic credits. |

The command mirrors the webhook's code path: creates the `IncomingEmail` row, enqueues `create_incoming_email_notification`, enqueues `classify_incoming_email`. It does NOT go through the HMAC + rate-limit shell because those are HTTP-surface concerns.

Source: [backend/email_organiser/management/commands/simulate_inbound_email.py](../backend/email_organiser/management/commands/simulate_inbound_email.py).

## AI configuration

| Setting | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | empty | If unset, `_call_claude()` logs a warning and returns `None`. Pipeline falls back to deterministic defaults per stage — no exceptions raised. |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Snapshotted on every `AISuggestionFeedback` row at create time so the labelled dataset stays interpretable after a model change. |

Cost guards:

- Classifier: 512 tokens, no contract context in the prompt.
- Topic agent: 2048 tokens, contract truncated at upload time (pypdf's extraction caps are per-file).
- Timeline generator: 512 tokens.
- Suggested reply: ~1024 tokens.

Per-email worst case: ~4 K tokens out (plus contract-sized input context on stage 2). For a supplier email on a mid-sized contract (50 KB text), that's typically a few cents per email on Sonnet 4.6 pricing.

Failure handling (all stages):
- No API key set → skip AI call, use defaults, still persist.
- API 5xx / timeout → `_call_claude()` returns `None`; the stage uses its deterministic fallback (classifier: relevant+medium+general; topic agent: empty strings).
- Celery retry: each task has `max_retries=2, default_retry_delay=60`. A task that raises (e.g. DB unreachable) is retried twice at 60 s intervals, then given up on.

## Permissions

- **Read** (`IncomingEmailListView`, `IncomingEmailDetailView`, `EmailAnalysisDetailView`, `IncomingEmailResolveView`, `IncomingEmailReanalyseView`) — any project member (managers always).
- **Inbound webhook** — the shared secret is the entire auth, no user required.
- Cross-project targets on the AI feedback endpoint return 404 (not 403) so project existence doesn't leak across accounts.

## Failure modes

| Symptom | Likely cause | Where to look |
|---|---|---|
| Email received by Brevo but no `IncomingEmail` row | HMAC mismatch (webhook returned 401) | Brevo delivery log + [backend logs for `InboundEmailWebhook`](../backend/email_organiser/views.py#L214) |
| `InboundEmailWebhook: INBOUND_EMAIL_WEBHOOK_SECRET is not configured` in logs | env var not set | [production.py](../backend/config/settings/production.py); base.py reads `INBOUND_EMAIL_WEBHOOK_SECRET` |
| Classification row created but `category=general, relevance=medium` for every email | AI key unset OR JSON parsing failing | Logs for `_call_claude: ANTHROPIC_API_KEY not set` or `classify_incoming_email: AI classification failed` |
| Analysis stuck `is_processed=False` | Stage 2 crashed; Celery retries exhausted | Celery worker logs; check `EmailAnalysis.objects.filter(email_id=...)` exists |
| Duplicate rows for the same email | Provider retried with a different `message_id` | Almost always a provider config issue — check the upstream parser. Our dedupe is keyed on `message_id` only. |
| Timeline event not created for relevant emails | Stage 3 timed out OR `deadline_days` missing from AI response | Check `EmailAnalysis.generated_timeline_event`; if null, re-run via the Re-analyse button in the UI. |

Emergency manual re-run for a stuck email:

```python
docker compose exec backend python manage.py shell -c "
from email_organiser.tasks import classify_incoming_email
classify_incoming_email.delay('<incoming-email-uuid>')
"
```

## Tests

No dedicated test file for the pipeline today; coverage sits in the broader backend suite ([backend/tests/](../backend/tests/)). The `simulate_inbound_email` command is the primary exercise path in dev. When adding new prompts or stages, pair with a fixture email in `tests/conftest.py` `incoming_email_factory` and exercise the task with `CELERY_TASK_ALWAYS_EAGER=True`.

## Known gaps / TODO

- **No outbound-send wiring** for suggested replies. `FinalResponse` rows exist in `status=suggested` but there's no "send" button — the user copy-pastes into their mail client today. Next phase: wire the Brevo SMTP relay we're already using for transactional mail.
- **No cost guard in code.** The classifier and topic agents use `max_tokens` caps but there's no per-project or per-tenant budget ceiling. Easy to add as a daily rollup + a cache-key check before `_call_claude()`.
- **Prompts are inline.** They live as module-level constants in `tasks.py`. Moving them to a `prompts/` subdirectory with one file per agent would simplify A/B testing. No users feeling pain yet.
- **Stage 4 (suggested reply) is the least-tested stage.** The prompt is the simplest but the downstream `FinalResponse` UI is embryonic.
- **Dedicated task retry policy.** `max_retries=2, default_retry_delay=60` is the same everywhere — fine for now. When a stage develops distinct failure profiles, split the retry policy per stage.

## Pointers

- [backend/email_organiser/tasks.py](../backend/email_organiser/tasks.py) — all four pipeline stages + prompts + `_call_claude` helper
- [backend/email_organiser/views.py](../backend/email_organiser/views.py) — webhook + list/detail + resolve/reanalyse
- [backend/email_organiser/management/commands/simulate_inbound_email.py](../backend/email_organiser/management/commands/simulate_inbound_email.py) — dev harness
- [frontend/src/components/email-organiser/](../frontend/src/components/email-organiser/) — the two UI panels
- [docs/research.md §A.1](research.md#a1-ai-suggestion-thumbs) — AI thumbs program spec
- [docs/AI_API.md](AI_API.md) — AI API contract (prompt/response shapes)
- [docs/deploy_runbook.md §5](deploy_runbook.md) — Brevo inbound parsing wiring

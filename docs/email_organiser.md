# Email Organiser Features

> Template. One section per capability inside the `email_organiser` app. Delete the "Template" section once you add your first real entry.

Component root: [backend/email_organiser/](../backend/email_organiser/). High-level diagram: [EmailOrganiser.drawio](../EmailOrganiser.drawio).

Upstream dependencies: Anthropic API (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`), an inbound-email webhook from SES/SendGrid/Postmark (secured via `INBOUND_EMAIL_WEBHOOK_SECRET`).

---

## Feature: {{feature name}}

**Status:** {{proposed | in-progress | shipped}}
**Owner:** {{name}}
**Pipeline stage:** {{ingest | classify | analyse | suggest | deliver}}

### Summary
One or two sentences on what this part of the pipeline does.

### Trigger
- Webhook `POST /api/email-organiser/inbound/` (see [email_organiser/views.py](../backend/email_organiser/views.py))
- Celery task `app.tasks.xxx` fired by …
- Scheduled (celery-beat entry)

### Data flow
1. Source → where the data lands (`IncomingEmail`, `EmailClassification`, …)
2. Transformation → which task / service runs
3. Output → model updated, notification emitted, AI suggestion stored

### Model(s) touched
- `IncomingEmail`
- `EmailClassification`
- `AiSuggestion`
- …

### AI interaction (if any)
- Prompt template: `email_organiser/prompts/xxx.py`
- Model: `ANTHROPIC_MODEL` (default `claude-sonnet-4-6`)
- Caching: prompt prefix cached / not cached
- Cost guard: max tokens, fallback on 429

### Permissions / access
Who can read the resulting records, which viewset exposes them.

### Failure modes
- Bad payload → how it's rejected
- AI timeout / 5xx → retry policy, fallback behavior
- Webhook replay → idempotency via `message_id`

### Tests
- `backend/email_organiser/tests/test_*.py`

### Known gaps / TODO
- [ ] ...

---

## Feature: (next one)

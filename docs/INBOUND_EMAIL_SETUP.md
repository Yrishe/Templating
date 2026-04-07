# Inbound Email Setup (Phase 3, item 8)

This document explains how to wire incoming email from a real provider into the
`POST /api/webhooks/inbound-email/` endpoint. Until this is configured, the
endpoint exists and is callable with a manual JSON payload, but no real mail
will reach it.

## How it fits together

1. A client sends an email to a project's auto-generated `generic_email`
   address — e.g. `proj-12345678@inbound.contractmgr.app`.
2. Your inbound provider (SES Inbound, SendGrid Inbound Parse, Postmark, etc.)
   receives the message and POSTs a parsed JSON payload to
   `/api/webhooks/inbound-email/`.
3. The webhook view authenticates via the `X-Webhook-Secret` header
   (set `INBOUND_EMAIL_WEBHOOK_SECRET` in the environment), looks up the
   project by `to` address, and creates an `IncomingEmail` record.
4. The new `IncomingEmail` triggers the
   `email_organiser.tasks.generate_suggested_reply` Celery task, which calls
   Claude with the project's contract text as context (Phase 3 items 9 + 10).
5. The resulting `FinalResponse` (status `suggested`, `is_ai_generated=True`)
   appears in the Email Organiser panel for the user to review and edit.

## Webhook payload (provider-agnostic)

```json
{
  "from": "client@example.com",
  "from_name": "Acme Client",
  "to": "proj-12345678@inbound.contractmgr.app",
  "subject": "Re: Contract terms",
  "body_plain": "Plain text body...",
  "body_html": "<p>HTML body...</p>",
  "message_id": "<unique-message-id@mail.example.com>",
  "received_at": "2026-04-07T12:00:00Z"
}
```

Headers required:

```
X-Webhook-Secret: <value of INBOUND_EMAIL_WEBHOOK_SECRET>
Content-Type: application/json
```

## Recommended provider: AWS SES Inbound

SES is already in your stack for outbound mail, so reusing it keeps the bill
on a single account.

### One-time setup

1. **Verify a domain you own** in SES (e.g. `inbound.contractmgr.app` — pick
   a subdomain dedicated to inbound mail).
2. **Add the MX record** SES gives you to that subdomain's DNS:
   ```
   inbound.contractmgr.app.  MX  10 inbound-smtp.eu-west-1.amazonaws.com.
   ```
3. **Create an SES Receipt Rule Set** with one rule that matches the catch-all
   recipient `*@inbound.contractmgr.app` and has a single action: **publish to
   an SNS topic**.
4. **Create an SNS topic** (e.g. `contract-mgr-inbound-mail`) and subscribe an
   HTTPS endpoint pointing at your deployed
   `https://api.contractmgr.app/api/webhooks/inbound-email/`.
5. **Set the secret**: in production, set `INBOUND_EMAIL_WEBHOOK_SECRET` to
   a long random string and configure SNS to send a custom HTTP header with
   the same value (or sign with SNS's built-in signature verification — see
   the "Tightening" section below).

### Updating `PROJECT_INBOUND_DOMAIN`

The auto-generated email address suffix is currently:

```python
# backend/projects/views.py
PROJECT_INBOUND_DOMAIN = "inbound.contractmgr.app"
```

Change this constant to whatever subdomain you verified in SES. Existing
projects keep their old `generic_email` value — only newly created projects
will use the new domain.

## Alternative providers

| Provider | Setup time | Cost | Notes |
|----------|------------|------|-------|
| **AWS SES Inbound** | ~30 min | $0.10/1000 emails | Recommended — single AWS bill |
| **SendGrid Inbound Parse** | ~15 min | Free with paid plan | Cleanest webhook payload format |
| **Postmark Inbound** | ~15 min | $1.25/1000 | Best deliverability/support |
| **Mailgun Routes** | ~20 min | $0.80/1000 | Good for low volume |

All four POST a JSON-ish payload — you'll need a small adapter view per
provider to map their fields onto our generic shape above. SendGrid uses
multipart form data (not JSON), so its adapter would parse `request.POST`
instead of `request.data`.

## Tightening (production)

The current shared-secret check is fine for development. For production with
SES → SNS, replace the `X-Webhook-Secret` check with proper SNS signature
verification using the `boto3` SNS message validator. The webhook view's
`post()` method has a clear extension point for this — only the auth block
needs to change.

## Testing without a real provider

You can manually trigger the webhook with `curl`:

```bash
curl -X POST http://localhost:8000/api/webhooks/inbound-email/ \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: ${INBOUND_EMAIL_WEBHOOK_SECRET}" \
  -d '{
    "from": "test@example.com",
    "from_name": "Test Client",
    "to": "proj-12345678@inbound.contractmgr.app",
    "subject": "Question about clause 4",
    "body_plain": "Hi, can you confirm the SLA in clause 4 is 99.9%?",
    "message_id": "<test-1@example.com>",
    "received_at": "2026-04-07T12:00:00Z"
  }'
```

(Replace `proj-12345678` with the slug of an actual project's `generic_email`.)

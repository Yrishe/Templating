# Customer Support & Event Routing

How users reach the team, how conversations are tracked, and how feedback/support events are fanned out to the right tools.

This is the **operational counterpart** to [docs/research.md](research.md) — research captures *what users think*, support handles *what users need right now*.

---

## Goals

1. Give every user an obvious, low-friction way to reach a human: chat widget in-app, email fallback.
2. Keep all conversations in **one system of record** — no "it's in Slack, also in email, also someone DM'd me".
3. Route events (feedback, support tickets, alerts) through **a single bus** so destinations can be added/removed by the support lead without redeploying.
4. Don't build a helpdesk. Pick one.

---

## Tool choice — decision still open

Pick one of the three; all three integrate cleanly with the app. **Default recommendation: Chatwoot**, on the grounds that self-hosting keeps support transcripts (which include contract details) inside our own infra.

| Tool | Hosting | Cost | Good fit when | Why you might skip |
|---|---|---|---|---|
| **Chatwoot** | Self-host (Docker) or SaaS | Free (self-host) / $19+ pp/mo cloud | You want open-source, full data residency, email + web chat + API in one | Ops burden: another Postgres + Redis + Sidekiq to babysit |
| **Plain** | SaaS only | Free tier, then usage-based | You want a modern API-first helpdesk, minimal UI overhead, Linear-style feel | No self-host; SaaS-only data residency; smaller ecosystem |
| **Intercom / Zendesk** | SaaS | $$$ | You need phone, CSAT surveys, bots, and a mature ecosystem today | Expensive; feature surface dwarfs what we need |

**Decision owed by:** first production rollout. Until then, [Plan A.2](research.md#a2-general-app-feedback-widget) covers the basic "how do I tell you something is broken" path.

Below assumes **Chatwoot self-hosted** unless noted. Swap-out cost is low (the app integration is a handful of HTTP calls and one webhook).

---

## In-app surface

Two entry points, each optimised for a different mode:

1. **Live chat bubble** — Chatwoot website widget, embedded in the authenticated layout. Loads lazily so anonymous pages don't pull it. Pre-fills name/email from the current `User` so users don't re-type. Conversation ID stored on the `User` row after first contact for continuity.
2. **"Contact support" link** in the user menu → mailto to `support@<domain>`. Same inbox feeds Chatwoot; no separate queue to manage.

**Not in scope:** in-app ticket list, ticket status, KB search. Those live in Chatwoot's portal; we link out.

### Identity linking

Chatwoot identifies a conversation via a **contact identifier HMAC** — we pass `user.email` plus a SHA-256 HMAC signed with the Chatwoot HMAC secret. Guarantees users can't impersonate each other by editing the widget's email field.

```tsx
// frontend/src/components/support/ChatwootWidget.tsx (future)
const identifier = user.email
const identifierHash = await api.get<{ hash: string }>(
  `/api/support/identifier-hash/?identifier=${encodeURIComponent(identifier)}`
)
window.chatwootSDK.run({ websiteToken, baseUrl })
window.$chatwoot.setUser(identifier, { email: user.email, name: user.name, identifier_hash: identifierHash.hash })
```

Backend endpoint `/api/support/identifier-hash/` reads the HMAC secret from env, computes, returns. Rate-limited per user.

---

## Event bus — n8n

**Why n8n, not direct Django → each-destination webhooks:** destinations change more often than the app does. Adding "also post 1-stars to a new #vip-users Slack channel" should be a drag-and-drop change, not a Django migration + redeploy.

**Why n8n, not just Celery:** Celery is for *in-app* async work (extract PDF text, send NPS emails). The event bus is about *out-of-app* fan-out where non-engineers (PM, support lead) need to edit the flows.

### Deployment options

- **Self-host alongside the compose stack** — add an `n8n` service to [docker-compose.yml](../docker-compose.yml), share the docker network. No per-seat cost, shared infra, single pane of glass.
- **n8n Cloud** — managed, faster to start, usage-based pricing. Pick if no one wants to operate another service.

Decision owed by: **when the first fan-out flow is wired**. Till then, destinations can be hardcoded.

### Flows to build

Each flow lives as an n8n workflow file checked into `infra/n8n/` (git-tracked JSON export), so they're reviewable and restorable.

**F1 — App feedback triage**
Trigger: Django webhook `POST <n8n>/webhook/app-feedback` with payload `{id, user_id, rating, route, created_at}`.
Nodes:
1. Rating ≤ 2 → Slack `#product-alerts` with message + link to admin page.
2. Rating ≥ 4 → daily digest email (buffered in a Google Sheet, sent via SMTP at 09:00).
3. Always → append row to Notion "Feedback log" DB.

**F2 — AI 👎 digest**
Trigger: nightly cron → HTTP GET `<backend>/api/feedback/ai/daily-down/` (returns last 24 h of 👎, behind an internal API key).
Nodes:
1. Group by `target_type`, count, top reasons.
2. POST Slack `#ai-quality` at 09:00 daily.

**F3 — Chatwoot → Linear**
Trigger: Chatwoot webhook `conversation.resolved`.
Nodes:
1. Extract "Feature request" / "Bug" labels from the Chatwoot conversation.
2. Create a Linear issue in the right project via Linear API.
3. Reply in Chatwoot with the Linear issue URL.

**F4 — NPS low-score follow-up**
Trigger: Django webhook when `NpsResponse.score ≤ 6`.
Nodes:
1. Look up `ResearchConsent` for the user via backend API.
2. If consented → add to "interview candidates" Notion DB with the NPS comment.
3. Slack `#customer-success` with a heads-up.

**F5 — Security event escalation** (bonus; low volume)
Trigger: Django webhook on repeated 401/429 bursts from a single source IP at the inbound-email webhook.
Nodes: PagerDuty + Slack `#oncall`.

### Webhook security

Every outbound webhook from Django uses:
- Shared secret in an env var (`N8N_FEEDBACK_WEBHOOK_SECRET`, `N8N_NPS_WEBHOOK_SECRET`, one per flow).
- `hmac.compare_digest` server-side on the n8n side too (n8n's "Webhook" node can enforce this).
- Signed over `body + timestamp`; reject if timestamp drift > 5 minutes to block replay.
- Pattern is the same one we just hardened for security finding #1.

### What stays in the bus, what doesn't

**On the bus:** IDs, ratings, route paths, timestamps, NPS scores, short status labels.
**Off the bus:** full feedback text, email bodies, contract content, PII beyond `user_id`. If a destination needs the content, it calls back into the backend with a service token and fetches it.

---

## SLA expectations

Written down so "we'll get back to you soon" has a meaning:

| Severity | First response | Resolution target |
|---|---|---|
| P0 — production down | 30 min | 4 h |
| P1 — blocking for one user | 4 h | 2 business days |
| P2 — non-blocking bug / question | 1 business day | 5 business days |
| P3 — feature request / feedback | 3 business days | triaged, not promised |

P0/P1 route through Chatwoot "priority" labels + PagerDuty via F5. P2/P3 follow normal triage in F1/F3.

---

## Security considerations

- Chatwoot stores message history including whatever users type. Treat it as PII-bearing.
- Self-hosted Chatwoot DB backups are in scope for the same retention policy as the app DB (see [REQUIREMENTS.md](../REQUIREMENTS.md) §6).
- HMAC secret for Chatwoot user identification goes in `.env` + `.env.example` (blank) following the pattern from security finding #12.
- n8n workflows can contain credentials — the n8n credential store uses its own encryption key; rotate quarterly and back it up separately from the workflow JSON.
- Don't wire n8n Cloud if contract text would touch it — self-host is safer for that use case.

---

## Implementation phases

**Phase S1 — Chatwoot standup** · ~2 days
Docker service + HMAC endpoint + widget embed + identity linking. Team gets a shared inbox.

**Phase S2 — n8n standup + F1 flow** · ~2 days
Service in compose, one end-to-end flow (App feedback → Slack + Notion) to validate the plumbing.

**Phase S3 — remaining flows F2-F5** · ~3 days
Iterate on destinations as ops team requests them.

**Phase S4 — SLA labels + PagerDuty** · ~2 days
Priority labels in Chatwoot, PagerDuty integration, on-call rotation documented.

**Phase S5 — tool re-evaluation** · rolling
After 3 months of use, review Chatwoot volume + ops cost. Switch to Plain or Intercom if self-host is eating more time than it saves.

---

## What this doesn't replace

- [docs/research.md](research.md) — research captures sentiment at rest; support captures pain in motion. Different flows, different audiences.
- [docs/AI_API.md](AI_API.md) — AI pipeline observability. Support tickets about AI failures feed back into AI thumbs data via F3.

---

_Last updated: 2026-04-19._

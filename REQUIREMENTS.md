# Project Requirements

Living document. Update as scope changes. For Python package requirements see [backend/requirements/](backend/requirements/); for npm packages see [frontend/package.json](frontend/package.json).

---

## 1. Purpose

A contract-and-project management platform with an AI-assisted email organiser. The system ingests project-scoped email, classifies and analyses it, and surfaces suggestions back to managers alongside the project/contract record it belongs to.

## 2. Users & roles

- **Admin** — manages accounts, roles, and global config.
- **Manager** — owns projects, approves contract state transitions, reviews AI suggestions.
- **Subscriber / member** — participates in projects, reads threads, uploads documents.

## 3. Functional requirements

### 3.1 Accounts
- Email + password authentication with JWT (access + refresh, rotation enabled).
- Role-based permissions enforced at API layer.

### 3.2 Projects
- CRUD on projects with tags, status, and a generic inbound email address.
- Timeline view aggregating contracts, notifications, and email events.

### 3.3 Contracts
- Upload PDF, extract text, track lifecycle state.
- Manager approval step before activation.
- Attachments with review comments.

### 3.4 Chat
- Per-project real-time chat (Django Channels over Redis).

### 3.5 Notifications
- In-app notifications for contract updates, chat, email classification.
- Mark-as-read state per recipient.

### 3.6 Email organiser
- Receive inbound emails via webhook (SES / SendGrid / Postmark compatible).
- Match to project by the project's generic email address.
- Classify email, analyse topic, generate timeline events.
- Optionally produce AI reply suggestions via Anthropic API.

### 3.7 Dashboard
- Aggregate view for a manager: recent activity, pending approvals, unread items.

## 4. Non-functional requirements

| Category | Target |
|---|---|
| Uptime (prod) | 99.5% |
| API latency | p95 < 300 ms for list endpoints at 1k project fixture size |
| Test coverage | ≥ 80% on backend (`pytest --cov`) |
| Accessibility | Frontend pages pass axe-core with no critical violations |
| Browser support | Last 2 versions of Chrome, Firefox, Safari, Edge |

## 5. Security requirements

See [docs/security.md](docs/security.md) for the current risk register. Baseline requirements:
- All secrets sourced from env vars; no defaults in production settings.
- Uploaded files gated by ownership/membership checks, not served publicly.
- Webhook authentication uses timing-safe comparison.
- JWTs not accessible to page scripts (`HttpOnly` cookies for refresh, in-memory access token).
- CSP enforced (not Report-Only).

## 6. Compliance & data

- Personal data in scope: user email, name, inbound email body/attachments.
- Retention: TBD (link to legal decision once taken).
- Backups: Postgres nightly snapshots, 30-day retention (target, not yet implemented).

## 7. External dependencies

| Service | Used for | Key env var |
|---|---|---|
| Anthropic API | Email classification + suggestion | `ANTHROPIC_API_KEY` |
| AWS SES (or SendGrid / Postmark) | Outbound email, inbound webhook | `AWS_SES_REGION_NAME` |
| Sentry | Error tracking (optional in dev) | `SENTRY_DSN` |

## 8. Environments

| Env | Settings module | Notes |
|---|---|---|
| Development | `config.settings.development` | `DEBUG=True`, console email backend, Docker Compose |
| Production | `config.settings.production` | `DEBUG=False`, secrets via env, external DB/Redis |

## 9. Out of scope (for now)

- Native mobile apps.
- Multi-tenant SSO (SAML / OIDC corporate providers).
- Payment processing.

## 10. Glossary

- **Project** — the top-level workspace; owns contracts, chats, and an inbound email address.
- **Contract** — a document lifecycle (draft → approval → active → archived) attached to a project.
- **Suggestion** — AI-generated reply draft produced by the email organiser.

---

_Last updated: 2026-04-19._

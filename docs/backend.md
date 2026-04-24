# Backend

End-to-end reference for the Django backend. Aimed at someone new to the codebase who needs to change an endpoint today.

## What it is

A Django REST Framework + Channels service that powers the contract-management product. Serves HTTP + WebSocket on the same ASGI app (Daphne), runs async work via Celery + Redis, persists to Postgres. Multi-role: **Manager** (platform oversight), **Account** (project owner), **Invited Account** (limited-rights member on someone else's project).

## Stack

| Layer | Tech |
|---|---|
| Framework | Django 5.0 + Django REST Framework 3.15 |
| Async protocol | Django Channels 4 (WebSocket) served via Daphne |
| Auth | SimpleJWT, refresh token in HttpOnly cookie, access token as Bearer |
| DB | PostgreSQL 16 |
| Cache / broker / channel layer | Redis 7 |
| Async tasks | Celery 5 (workers + beat) |
| AI | Anthropic Claude (email organiser pipeline) |
| OCR fallback | AWS Textract (optional — degrades to pypdf-only when unset) |
| File uploads | PDF magic-byte + structural (pypdf) validation + size cap |
| OpenAPI | drf-spectacular → `/api/schema/`, Swagger UI at `/api/docs/` |

## Project layout

```
backend/
  config/
    settings/
      base.py               # shared: DB, Redis, SimpleJWT, CORS, throttles, feature flags
      development.py        # DEBUG, SQLite fallbacks, eager Celery, relaxed CSP
      production.py         # HSTS, SSL redirect, fail-fast env, Sentry, SMTP
    asgi.py                 # ASGI mounting (HTTP + `websocket` protocol via Channels)
    urls.py                 # mounts /api/* + /admin/ + /api/schema|docs|redoc/
    celery.py               # Celery app + autodiscover_tasks
  accounts/                 # users, auth endpoints, manager approval
  projects/                 # projects, memberships, timelines, tags
  contracts/                # contract + change-request lifecycle
  chat/                     # per-project chat (REST + WebSocket consumer)
  email_organiser/          # AI email pipeline (ingest → classify → analyse → suggest)
  notifications/            # fan-out + actor-suppression + per-user dismissal
  dashboard/                # single-call /api/dashboard/ bundling home stats
  feedback/                 # 👍/👎 on AI outputs + per-feature feedback widget
  fixtures/                 # seed data (users, projects, contracts)
  tests/                    # all tests live here, one file per topic
  requirements/             # production.txt + development.txt (pytest, mypy, ruff)
```

## Conventions that load-bear

Get these right or the app misbehaves.

- **Permission boundary is the ORM filter, not the view.** Lists filter by `ProjectMembership` (or manager role for oversight); detail views reject with `404` not `403` when the user can't see the resource, so the endpoint doesn't leak existence cross-account.
- **Managers have global oversight on every project** (finding #8 in [security.md](security.md), accepted-risk). The permission check pattern is `if user.role == user.MANAGER: qs = qs.all()`. The per-project scoping design is deferred — multi-tenancy trigger.
- **Invited accounts must have a matching `ProjectMembership` row**, not just an `InvitedAccount`. The legacy `ProjectInviteView` creates both; direct `InvitedAccount.objects.create()` will silently 404 every nested route (see the regression test in [tests/test_permissions.py](../backend/tests/test_permissions.py)).
- **Rate limits are per-endpoint via `ScopedRateThrottle`.** Scopes live in `DEFAULT_THROTTLE_RATES` in [base.py](../backend/config/settings/base.py). Adding a new throttled endpoint means declaring `throttle_scope` on the view AND a rate in settings.
- **Feature flags are env-driven.** `FEATURE_<NAME>` in env → exposed via `/api/auth/me/features.<name>` → read by the frontend. See [accounts/serializers.py `UserProfileSerializer.get_features()`](../backend/accounts/serializers.py).
- **File uploads enforce magic-byte + structural + size validation at the serializer.** [contracts/serializers.py](../backend/contracts/serializers.py) rejects non-PDF polyglots. Client-side size checks are UX hints only.
- **Authenticated file downloads** stream via `ContractDownloadView` / `ContractRequestAttachmentView`. `MEDIA_URL` is NOT publicly served in production ([config/urls.py:31](../backend/config/urls.py#L31)). Frontend fetches blobs with `Authorization: Bearer` via [downloadAuthed()](../frontend/src/lib/api.ts).

## Apps

Each section lists the models, endpoints, permission shape, and async work. Internal service modules and prompts are called out where relevant.

### accounts

Users, authentication, manager-approval workflow.

**Models:** `User` (custom — role + UUID pk + email-as-username), `Account` (subscriber record for manager-tracked billing-ish data).

**Roles:** `manager`, `account` (aka subscriber), `invited_account`.

**Endpoints** (mounted under `/api/auth/`):

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| POST | `/signup/` | `SignupView` | AllowAny | `role=manager` lands `is_active=false` pending approval. `role=invited_account` is rejected here — only managers can invite. Throttle `auth` (10/min). |
| POST | `/login/` | `LoginView` | AllowAny | Returns `{user, access}` + sets HttpOnly refresh cookie. Throttle `auth`. |
| POST | `/logout/` | `LogoutView` | AllowAny | Reads the refresh cookie, blacklists, clears cookie. Idempotent. |
| POST | `/token/refresh/` | `TokenRefreshCookieView` | AllowAny | Reads cookie (NOT body — legacy body-refresh returns 401). Rotates refresh, returns `{access}`. Throttle `auth_refresh` (30/min). |
| GET | `/me/` | `MeView` | IsAuthenticated | Current user with `features` block (flag values). |
| PATCH | `/me/` | `MeView` | IsAuthenticated | Update own profile fields. |
| GET | `/users/search/?q=...&role=...` | `UserSearchView` | IsAuthenticated | For invite UI; max 20 results. |
| GET / POST | `/accounts/` | `AccountListCreateView` | IsAuthenticated + IsSubscriber | |
| GET / PUT / DELETE | `/accounts/<pk>/` | `AccountDetailView` | IsAuthenticated + IsAccountOwner | |
| GET | `/pending-managers/` | `PendingManagerListView` | Active manager | |
| POST | `/pending-managers/<pk>/approve/` | `PendingManagerApproveView` | Active manager | Flips `is_active=True`. |
| POST | `/pending-managers/<pk>/reject/` | `PendingManagerRejectView` | Active manager | Deletes the pending user row. |

**Auth model (Security #5):** detailed in [security_5_plan.md](security_5_plan.md). Refresh cookie scoped to `/api/auth/` only; access token never persisted client-side.

**Tests:** [tests/test_auth.py](../backend/tests/test_auth.py) — 18 tests covering signup/login/refresh/logout/cookie shape/legacy-body-rejection guardrail.

### projects

Projects, memberships, timelines, tags.

**Models:** `Project`, `ProjectMembership`, `Timeline`, `TimelineEvent`, `TimelineComment`, `Tag`.

On `Project` create, the server auto-provisions `generic_email` (unique per project, used by the inbound email webhook), a `Timeline`, a `Chat`, and an `EmailOrganiser`.

**Endpoints:**

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET / POST | `/api/projects/` | `ProjectListCreateView` | IsAuthenticated | Non-managers see only projects they're a member of. Managers see all. |
| GET / PATCH / DELETE | `/api/projects/<pk>/` | `ProjectDetailView` | IsAuthenticated | Same scoping; 404 for non-members. |
| GET | `/api/projects/<id>/timeline/` | `ProjectTimelineView` | Project member | |
| POST | `/api/projects/<id>/timeline/events/` | `TimelineEventCreateView` | Project owner OR manager | |
| GET / PATCH / DELETE | `/api/projects/<id>/timeline/events/<eid>/` | `TimelineEventDetailView` | Read: member. Write: owner/manager. | |
| GET / POST | `/api/projects/<id>/timeline/events/<eid>/comments/` | `TimelineCommentListCreateView` | Project member | 5 comment types. |
| GET | `/api/project-memberships/?project=<id>` | `ProjectMembershipListView` | IsAuthenticated | List view used by the frontend invite page. |
| POST | `/api/projects/<id>/members/` | `ProjectMemberAddView` | Manager OR account owner of the project | `{user_id}` or `{email}`. Email must match an existing active User or 400. |
| GET / POST | `/api/tags/` | `TagListCreateView` | IsAuthenticated | Shared tag pool. |
| GET / DELETE | `/api/tags/<pk>/` | `TagDetailView` | IsAuthenticated | |

**Business logic:** project creation in `ProjectListCreateView.perform_create` ([projects/views.py](../backend/projects/views.py)) — auto-generates `generic_email` as `proj-<uuid8>@inbound.contractmgr.app`, creates membership + timeline + chat + email_organiser rows.

**Tests:** [tests/test_permissions.py](../backend/tests/test_permissions.py) covers project visibility, contract visibility, mutation permissions, membership visibility, invite→membership symmetry.

### contracts

One OneToOne contract per project + free-form change requests with optional PDF attachments.

**Models:** `Contract`, `ContractRequest`.

Contract statuses: `draft` → `active` → `expired`. Activation is manager-gated and also fires from the change-request approval path.

**File uploads** — PDF only, 10 MB cap in the serializer, 15 MB cap at middleware. Validator parses via `pypdf.PdfReader` after magic-byte sniff — rejects polyglots.

**Endpoints:**

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET / POST | `/api/contracts/?project=<id>` | `ContractListCreateView` | Project member (manager sees all) | |
| GET / PATCH / DELETE | `/api/contracts/<pk>/` | `ContractDetailView` | Member read; account-owner or manager write | |
| POST | `/api/contracts/<pk>/activate/` | `ContractActivateView` | Manager | Flips status to `active` + sets `activated_at`. |
| GET | `/api/contracts/<pk>/download/` | `ContractDownloadView` | Project member | Streams the PDF after auth check. |
| GET / POST | `/api/contract-requests/?project=<id>` | `ContractRequestListCreateView` | Project member | Statuses: pending/approved/rejected. |
| GET / PATCH | `/api/contract-requests/<pk>/` | `ContractRequestDetailView` | Member | |
| POST | `/api/contract-requests/<pk>/approve/` | `ContractRequestApproveView` | Manager | Auto-activates a draft contract. |
| POST | `/api/contract-requests/<pk>/reject/` | `ContractRequestRejectView` | Manager | Requires `review_comment`. |
| GET | `/api/contract-requests/<pk>/attachment/` | `ContractRequestAttachmentView` | Member | Streams the attachment. |

**Text extraction.** On contract upload the serializer pulls text via pypdf; if empty (scanned PDF) AND `AWS_REGION` is set, a Celery task invokes Textract as a fallback. Result lands in `contract.content` with `text_source` = `pypdf` / `textract` / `manual` / `none`.

**Tests:** [tests/test_contracts.py](../backend/tests/test_contracts.py) — upload validation, mutation permissions, approve/reject flow, activation cascade.

### chat

Real-time per-project chat with a REST fallback.

**Models:** `Chat` (one per project, auto-created), `Message`.

**Transport.** Primary channel is a WebSocket at `/ws/chat/<project_id>/?token=<access>`. The frontend also polls `GET /api/chats/<id>/messages/` every 5 s so chat keeps working when WS drops.

**Auth on WS upgrade:** [chat/consumers.py `ChatConsumer.connect`](../backend/chat/consumers.py) parses `?token=` from the query string, verifies via SimpleJWT, then checks `ProjectMembership`. 4001 if token invalid, 4003 if not a member.

**Endpoints** (mounted under `/api/`):

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET | `/chats/<project_id>/` | `ChatDetailView` | Project member | Auto-creates the Chat row if missing. |
| GET / POST | `/chats/<project_id>/messages/` | `MessageListView` | Project member | POST also broadcasts to the WS group and fires a `chat_message` notification. |

**Channels config:** [base.py:241](../backend/config/settings/base.py#L241) — `RedisChannelLayer` on `REDIS_HOST:REDIS_PORT`.

### email_organiser

Full detail in [email_organiser.md](email_organiser.md). Summary: inbound webhook → HMAC verify → dedupe by `message_id` → create `IncomingEmail` → Celery chain (classify → analyse by topic → optional timeline event → optional suggested reply).

**Endpoints** (mounted under `/api/`):

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET | `/projects/<id>/incoming-emails/` | `IncomingEmailListView` | Project member | Filters: category, relevance, is_resolved, is_relevant. |
| GET | `/projects/<id>/incoming-emails/<pk>/` | `IncomingEmailDetailView` | Member | With nested analysis. |
| POST | `/projects/<id>/incoming-emails/<pk>/resolve/` | `IncomingEmailResolveView` | Member | Mark occurrence resolved. |
| POST | `/projects/<id>/incoming-emails/<pk>/reanalyse/` | `IncomingEmailReanalyseView` | Member | Clear + re-enqueue. |
| GET | `/projects/<id>/incoming-emails/<pk>/analysis/` | `EmailAnalysisDetailView` | Member | |
| POST | `/webhooks/inbound-email/` | `InboundEmailWebhookView` | Webhook secret | HMAC via `X-Webhook-Secret`. Throttle `inbound_email` (60/min). Payload >256 KB is stored as `{size, sha256, _truncated}` only. |
| GET / PATCH | `/email-organiser/<project_id>/` | `EmailOrganiserDetailView` | Member | Per-project config + AI context. |
| POST | `/projects/<id>/invite/` | `ProjectInviteView` | Manager | Legacy invite endpoint; creates InvitedAccount + mirrored ProjectMembership. |
| GET | `/projects/<id>/invited-accounts/` | `InvitedAccountListView` | Member | |

**Dev helper:** `python manage.py simulate_inbound_email --project <id_or_email>` fires the same Celery fan-out without a live mailbox. See the management command for flags.

### notifications

Fan-out for project events + outbound email audit log.

**Models:** `Notification` (12 types, see [models.py](../backend/notifications/models.py)), `OutboundEmail`.

**Types:** `contract_request`, `contract_request_approved`, `contract_request_rejected`, `contract_update`, `chat_message`, `new_email`, `deadline_upcoming`, `timeline_comment`, `email_high_relevance`, `email_occurrence_unresolved`, `manager_alert`, `system`.

**Endpoints:**

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET | `/api/notifications/?project=<id>&is_read=...` | `NotificationListView` | IsAuthenticated | Actor-suppressed (you never see your own actions); per-user dismissal. |
| POST | `/api/notifications/<pk>/read/` | `NotificationMarkReadView` | IsAuthenticated | Per-user dismissal — doesn't hide for other members. |
| POST | `/api/notifications/mark-all-read/` | `NotificationMarkAllReadView` | IsAuthenticated | Bulk dismissal for the caller. |
| GET | `/api/notifications/emails/` | `OutboundEmailListView` | Manager | Audit trail of outbound emails. |

**Load-bearing invariant** ([notifications/views.py](../backend/notifications/views.py)): the actor-suppression filter is `.filter(Q(actor__isnull=True) | ~Q(actor=user))` — the Q-object form is deliberate; plain `.exclude(actor=user)` drops NULL-actor rows (deadline reminders, system alerts).

**Async tasks** ([notifications/tasks.py](../backend/notifications/tasks.py)): each event-producing view calls `create_<type>_notification.delay(...)`. Failures are logged but not fatal — the originating action already persisted.

### dashboard

One endpoint, one view — returns the home-screen bundle in a single round-trip.

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| GET | `/api/dashboard/` | `DashboardView` | IsAuthenticated | `{role, unread_notification_count, project_count, completed_projects, recent_notifications, recent_projects, pending_contract_requests, active_contracts, account_count, pending_manager_count}`. |

Role-aware — managers see pending-manager count + pending-contract-request count. Accounts see their own projects.

### feedback

Two surfaces. Both use idempotent upsert so re-POSTs update rather than duplicate.

**Phase 1 — AI thumbs** (shipped 2026-04-20).

Model: `AISuggestionFeedback` keyed on `(user, target_type, target_id)`. `target_type` ∈ {`classification`, `suggestion`, `timeline_event` (reserved)}. Snapshots `model` + `provider` on create so the eval dataset stays readable after `ANTHROPIC_MODEL` changes.

**Phase 1.5 — per-feature feedback** (shipped 2026-04-22).

Model: `FeatureFeedback` keyed on `(user, feature_key, project)`. `feature_key` is free-form dotted (e.g. `dashboard.home`, `projects.overview`). `project` is nullable for app-global features. `comment` max 1000 chars.

**Endpoints:**

| Method | Path | View | Perm | Notes |
|---|---|---|---|---|
| POST | `/api/feedback/ai/` | `AISuggestionFeedbackView` | IsAuthenticated + project visibility | Throttle `ai_feedback` (30/min). |
| POST | `/api/feedback/feature/` | `FeatureFeedbackView` | IsAuthenticated + project visibility (if project supplied) | Throttle `feature_feedback` (20/min). |

**Tests:** [tests/test_ai_feedback.py](../backend/tests/test_ai_feedback.py) + [tests/test_feature_feedback.py](../backend/tests/test_feature_feedback.py).

## Cross-cutting concerns

### Authentication & authorization

- **JWT via SimpleJWT.** 15-min access, 24-h refresh, rotation + blacklist-after-rotation.
- **Refresh token lives in an HttpOnly cookie** scoped to `/api/auth/` ([accounts/views.py `_set_refresh_cookie`](../backend/accounts/views.py)). Cookie attributes: `Secure` in prod, `SameSite=Strict`, `Path=/api/auth/`. Body-refresh is a hard 401 — no legacy fallback.
- **Access token** arrives as `Authorization: Bearer`. The `CookieJWTAuthentication` class is a no-op wrapper over `JWTAuthentication` — renaming it would break the production auth config, but it no longer reads cookies (see [accounts/authentication.py](../backend/accounts/authentication.py)).
- **Manager global oversight** — every list view has a `if user.role == user.MANAGER: qs = qs.all()` branch. Per-project manager scoping is the deferred design in [security.md finding #8](security.md#8).

### Throttling

Four scopes defined in [base.py](../backend/config/settings/base.py) `DEFAULT_THROTTLE_RATES`:

| Scope | Rate | Used by |
|---|---|---|
| `anon` | 60/hour | default on every view |
| `user` | 2000/day | default on every view |
| `auth` | 10/minute | login, signup |
| `auth_refresh` | 30/minute | token refresh |
| `inbound_email` | 60/minute | webhook |
| `ai_feedback` | 30/minute | AI thumbs |
| `feature_feedback` | 20/minute | per-feature feedback |

Scoped throttle state lives in Django's default cache (LocMemCache in tests, Redis in prod). Test isolation clears the cache between runs — see [tests/conftest.py](../backend/tests/conftest.py) `_reset_cache`.

### Settings split

| File | Role |
|---|---|
| [base.py](../backend/config/settings/base.py) | Shared config. Dev-safe defaults only where they can't cause a prod footgun. |
| [development.py](../backend/config/settings/development.py) | DEBUG, local DB fallbacks, eager Celery (`CELERY_TASK_ALWAYS_EAGER=True`), loose CORS. |
| [production.py](../backend/config/settings/production.py) | Fail-fast `_require_env('DJANGO_SECRET_KEY')`, HSTS + SSL redirect, Sentry if `SENTRY_DSN` set, `ManifestStaticFilesStorage`. |

### Celery

One worker + one beat. Tasks live next to the app: `accounts/tasks.py`, `email_organiser/tasks.py`, `notifications/tasks.py`, `contracts/tasks.py`. Broker and result backend both Redis (same instance, different logical DBs in dev).

### OpenAPI / Swagger

`drf-spectacular` auto-generates a schema at `/api/schema/`. Human-readable browsers at `/api/docs/` (Swagger UI) and `/api/redoc/` (ReDoc). No `COMPONENT_SPLIT_REQUEST` gotchas — request/response schemas are separate components.

## Environment variables

Required in prod (`_require_env` raises if missing):

| Var | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | JWT signing + crypto signer |
| `DJANGO_ALLOWED_HOSTS` | comma-separated; empty → startup refuses |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | Postgres connection |
| `INBOUND_EMAIL_WEBHOOK_SECRET` | HMAC for inbound webhook (webhook 503s without it) |
| `ANTHROPIC_API_KEY` | Claude API (pipeline degrades gracefully without it) |

Optional / configurable:

| Var | Default / purpose |
|---|---|
| `DB_PORT` | `5432` |
| `REDIS_HOST`, `REDIS_PORT` | `127.0.0.1` / `6379` |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | derived from Redis by default |
| `CORS_ALLOWED_ORIGINS` | comma-separated |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | prod SMTP (Brevo in our deploy) |
| `DEFAULT_FROM_EMAIL` | |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Textract OCR fallback |
| `SENTRY_DSN` | error tracking |
| `FEATURE_AI_THUMBS`, `FEATURE_FEATURE_FEEDBACK` | feature flags |

## Testing

All tests live under [backend/tests/](../backend/tests/) — one file per topic, not per app. Currently 132 passing.

| File | Covers |
|---|---|
| `test_auth.py` | Signup / login / refresh / logout / cookie shape / legacy-body rejection |
| `test_permissions.py` | Project / contract visibility, mutation gates, invite → membership symmetry |
| `test_contracts.py` | Upload validation, approve/reject, activation cascade |
| `test_notifications.py` | Actor suppression, per-user dismissal, manager oversight, 12 notification types round-trip |
| `test_ai_feedback.py` | AI thumbs upsert, permissions, validation, throttle, `/me` flag |
| `test_feature_feedback.py` | Per-feature feedback upsert, app-global vs project-scoped, validation, throttle |
| `test_schema.py` | Migrations applied, required columns, fixture loads |

Run locally: `docker compose exec backend python -m pytest` (132 tests, ~60 s). CI: [.github/workflows/backend-ci.yml](../.github/workflows/backend-ci.yml) with 80% coverage gate + ruff + mypy + migration check.

## Dev helpers

| Command | Purpose |
|---|---|
| `python manage.py migrate` | Apply schema. |
| `python manage.py loaddata fixtures/users.json fixtures/initial_data.json` | Seed dev data. |
| `python manage.py createsuperuser` | First-manager bootstrap; see [deploy_runbook.md §1.6](deploy_runbook.md). |
| `python manage.py simulate_inbound_email --project <id_or_email> --subject <s>` | Fire the webhook path without a live mailbox. Supports `--skip-classify`. |
| `python manage.py shell` | Ad-hoc queries; throttle cache reset: `from django.core.cache import cache; cache.clear()`. |

## Known gaps / TODO

- **Per-project manager scoping** ([security.md finding #8](security.md#8)) — every list view currently has a `if user.role == MANAGER: qs = qs.all()` branch. Precondition for multi-company tenancy.
- **OpenAPI request/response examples** — spectacular auto-generates schemas but no handcrafted examples on the endpoints. Low priority until external integrators exist.
- **Celery retry policy** — tasks declare `max_retries=2, default_retry_delay=60`, but no dead-letter queue. A classified email that fails analysis three times stays `is_processed=False` forever. Candidate for a monthly sweeper task.
- **Bulk notification mark-read** per-project — the current `mark-all-read` clears every notification for the user, not per-project. Add a `?project=<id>` filter when needed.
- **Scheduled task inventory** — only one beat schedule today (deadline reminders). Document the full schedule as beat entries grow.

## Pointers

- [README.md](../README.md) — project overview, stack, role matrix
- [docs/frontend.md](frontend.md) — frontend counterpart
- [docs/email_organiser.md](email_organiser.md) — AI pipeline deep-dive
- [docs/security.md](security.md) + [docs/security_5_plan.md](security_5_plan.md) — security posture + auth-storage rationale
- [docs/deploy_runbook.md](deploy_runbook.md) — production ops
- [RUNNING.md](../RUNNING.md) — first-run setup walkthrough

# ContractMgr

Multi-role contract and project management platform. Accounts create projects and upload contracts; managers review change requests; every project has its own real-time chat, email organiser (AI-assisted), and timeline.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router) + TypeScript + Tailwind + TanStack Query |
| Backend | Django 5.0 + Django REST Framework 3.15 |
| Real-time | Django Channels 4 + Redis (WebSockets) |
| Async tasks | Celery 5 + Redis |
| Database | PostgreSQL 16 |
| Auth | SimpleJWT with per-tab `sessionStorage` + `Authorization: Bearer` |
| AI (email organiser) | Anthropic Claude (narrowed knowledge per-contract RAG) |
| Hosting target | AWS ECS Fargate / Google Cloud Run |

## Roles

- **Manager** — platform oversight; reviews change requests, approves manager signups, has read access to every project.
- **Account** — creates projects, uploads contracts, raises change requests. Can invite other users to their projects.
- **Invited Account** — added to a project by a member; can chat, raise change requests, and use the email organiser, but cannot upload or edit contracts directly.

## Key features

- **Projects** — each has an auto-generated inbound email, a single Contract (OneToOne), a real-time Chat, a Timeline, and an Email Organiser.
- **Change requests** — Accounts can raise unlimited change requests against a contract, each with an optional PDF attachment. Managers approve or reject with a justification comment. Approval auto-activates a draft contract. Full history lives on a dedicated `Change Requests` tab.
- **Notifications** — per-project feed with 9 types (`contract_request`, `contract_request_approved/_rejected`, `contract_update`, `chat_message`, `new_email`, `deadline_upcoming`, `manager_alert`, `system`). Actor-suppressed (nobody sees their own actions), per-user dismissible, click-through deep-linked.
- **Multi-tab sessions** — auth tokens live in per-tab `sessionStorage`, so two users can work side-by-side in the same browser (e.g. `Manager` in tab A, `Account` in tab B). Cookies are per-origin; `sessionStorage` is per-tab.
- **Dark mode** — light / dark / system theme selector in Settings, driven by a `ThemeProvider` + `.dark` class on `<html>`.
- **AI-assisted replies** — inbound email ingestion (SES / SendGrid) fires a Celery task that asks Claude for a suggested reply using the project's contract as narrowed knowledge.

## Getting started

### Docker Compose (recommended)

```bash
cp .env.example .env
# edit .env — at minimum set DJANGO_SECRET_KEY, POSTGRES_USER, POSTGRES_PASSWORD, ANTHROPIC_API_KEY
docker compose up --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py loaddata fixtures/*.json   # optional sample data
```

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend API (Django) | http://localhost:8000/api/ |
| API schema (Swagger) | http://localhost:8000/api/docs/ |
| Django admin | http://localhost:8000/admin/ |

### Local (no Docker)

Requires Python 3.12+, Node 20+, PostgreSQL 16, Redis 7.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements/development.txt
python manage.py migrate
python manage.py runserver        # or: daphne -p 8000 config.asgi:application (needed for real-time chat)
celery -A config worker -l info   # separate terminal — or set CELERY_TASK_ALWAYS_EAGER=True in dev
```

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

## Tests

```bash
cd backend
pytest                            # 77 tests across auth / permissions / contracts / change requests / notifications / schema
pytest --cov=. --cov-report=term-missing
```

```bash
cd frontend
npm run type-check                # tsc --noEmit
npm run build                     # full Next.js production build
npm run lint
```

See **`docs/TESTING.md`** for test layout, what each file covers, and what's still missing.

## Docs

- **[`docs/SECURITY.md`](docs/SECURITY.md)** — security posture, threat model, known risks, hardening checklist.
- **[`docs/TESTING.md`](docs/TESTING.md)** — test inventory, coverage gaps, how to run.
- **[`docs/DEPLOYMENT_COSTS.md`](docs/DEPLOYMENT_COSTS.md)** — itemized cost estimate (hosting, Claude API, storage, email, etc.) with scale assumptions.
- **[`docs/N8N_INTEGRATION.md`](docs/N8N_INTEGRATION.md)** — how to plug n8n in for customer support / automation, and the security risks of doing so.
- **[`docs/INBOUND_EMAIL_SETUP.md`](docs/INBOUND_EMAIL_SETUP.md)** — SES / SendGrid inbound webhook configuration.
- **`PLANS.md`** — work items queued but not yet landed (file type/size limits ✅ done, CSP hardening, SES+SNS signature verification, deadline beat schedule, etc.).
- **`Diagram.drawio`** — 8-page architecture / flow diagram (ER view, system diagram, user journey, Phase 2 + 3, change request lifecycle, notification system, multi-tab auth).

## Conventions

- Every write endpoint enforces role + project membership server-side. See `backend/*/views.py` — look for the manager-oversight `_visible_projects_qs` helper in `notifications/views.py` and the mirrored patterns in `contracts/views.py`.
- File uploads go through PDF magic-byte + 10 MB size validators on the serializer (`contracts/serializers.py::_validate_pdf_upload`).
- Auth endpoints have a per-scope rate limit (`auth`: 10/min, `auth_refresh`: 30/min) — see `backend/config/settings/base.py::DEFAULT_THROTTLE_RATES`.
- Notifications suppress the actor (`NotificationListView.get_queryset` — `.filter(Q(actor__isnull=True) | ~Q(actor=user))`). The Q-object form is deliberate; plain `.exclude(actor=user)` silently drops NULL-actor rows. **Don't change this without reading the comment in `notifications/views.py`.**

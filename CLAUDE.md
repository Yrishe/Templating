# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Contract Management Web Application — a multi-role platform for managing contracts, projects, and communications. See `technical_specification.docx` and `project_plan.docx` for full detail.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js + TypeScript |
| Backend | Django + Django REST Framework |
| Real-time | Django Channels + Redis (WebSockets) |
| Async tasks | Celery + Redis |
| Database | PostgreSQL |
| Auth | django-allauth + DRF SimpleJWT (httpOnly cookies — never localStorage) |
| Hosting | AWS ECS Fargate / GCP Cloud Run |
| Email | AWS SES (or SendGrid TBD) |
| AI (email organiser) | TBD (Claude API / OpenAI) |

## Development stages

The project is built sequentially across 4 stages, each with a handoff checklist before the next begins:

1. **Stage 1 — Database schema design** ← *current*
2. **Stage 2 — Frontend design, testing & implementation**
3. **Stage 3 — Backend design, testing & implementation**
4. **Stage 4 — CI/CD pipelines & releases**

## Commands

Commands will be added as each stage produces runnable code. Planned commands per stage:

### Backend (Stage 3)
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
pytest                   # unit + integration tests
pytest --cov=. --cov-fail-under=80   # coverage gate
```

### Frontend (Stage 2)
```bash
npm install
npm run dev              # development server
npm run build && npm start
npm run lint             # ESLint
npm run type-check       # TypeScript
npm test                 # Jest
npm run test:e2e         # Playwright
```

## Architecture

### Layers
1. **Client** — Next.js (SSR + file-based routing); tokens in httpOnly cookies; CSP headers
2. **API** — Django REST Framework + Django Channels (WebSockets); Celery workers for async tasks
3. **Data** — PostgreSQL; Redis (Celery broker + session/channel layer store)
4. **Infra** — Containerised on AWS ECS Fargate or GCP Cloud Run; secrets via AWS Secrets Manager

### Core domain entities (17 total)

The key relationships to hold in mind:

- A **Subscriber** owns one or more **Accounts** and creates **Projects**.
- A **Project** has members, one **Contract**, a generic email address, and contains the **Project Management Page** (dashboard, chat, email organiser, timeline).
- A **Contract Request** is raised by an Account, reviewed by a **Manager**, and triggers **Notifications** which generate transactional **Emails**.
- The **Email Organiser** (AI-assisted) notifies **Invited Accounts** who can edit **Final Responses** before they are sent to **Recipients**.
- **Chat** is real-time (Django Channels/WebSockets); **Messages** are written by Managers or Accounts.

### Auth & permissions
- JWT tokens stored in httpOnly cookies (not localStorage).
- Three roles: **Manager** (full access), **Subscriber** (scoped to own accounts/projects), **Invited Account** (read/edit access to specific projects).
- DRF object-level permissions enforce per-role access at the API layer.

### Security conventions
- All DB access through Django ORM (parameterised queries).
- CSRF middleware always enabled.
- Rate limiting on auth and sensitive endpoints.
- TLS 1.2+ everywhere; AWS WAF + API Gateway at the network edge.

## Key documents
- `technical_specification.docx` — entity model, field types, security decisions, stack rationale
- `project_plan.docx` — 4-stage roadmap with tasks and handoff criteria per stage
- `Diagram.drawio` — system architecture / entity flow diagram

# Future Implementation Plans

Long-horizon work that is not scheduled yet. This doc keeps enough context so someone can pick up any item quickly.

---

## Current priorities and open decisions

### Recently landed

1. **Phase 1: AI-suggestion thumbs** (landed 2026-04-20, commit `1c99cc8`)
   - Added `POST /api/feedback/ai/`.
   - Added `<AiFeedback>` on email classifications and suggested replies.
   - Exposed `FEATURE_AI_THUMBS` via `/api/auth/me/`.
   - Verification: 13 feedback tests plus 116-suite pass.
   - Also fixed 7 unrelated pre-existing test failures in `9e09848`.

2. **Security #5: HttpOnly refresh cookie + in-memory access token** (landed 2026-04-21)
   - Refresh token now uses `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api/auth/`.
   - Access token now lives in a module-level ref in [frontend/src/lib/api.ts](../frontend/src/lib/api.ts).
   - Auth context bootstraps through `/api/auth/token/refresh/`.
   - Multi-tab different-users support was intentionally dropped.
   - No CSP changes (already enforced in production).
   - Full decisions are in [docs/security_5_plan.md](security_5_plan.md).

3. **Per-feature feedback widget (Phase 1.5)** (landed 2026-04-22)
   - `FeatureFeedback` model + `POST /api/feedback/feature/`; thumbs + optional comment keyed on (`user`, `feature_key`, `project`).
   - `<FeatureFeedback>` React component mounted on Dashboard, Project Overview, and Email-Organiser Analysis Panel.
   - Gated by `FEATURE_FEATURE_FEEDBACK` flag exposed through `/api/auth/me/features.feature_feedback`.
   - Intentionally narrower than the Phase 2 floating-button sketch in [docs/research.md](research.md); support-tool + n8n decisions are still deferred.

### Next up — path to first production deploy

Ordered work list + current-state snapshot lives in [docs/deployment_plan.md](deployment_plan.md). The single blocker is the hosting decision (Fly.io + Postmark / Scaleway + Brevo / Hetzner + Postmark — see [docs/hosting_plans.md](hosting_plans.md)); production Dockerfile + CI pipeline is the largest remaining work block and is hosting-agnostic, so it can start in parallel.

### Postponed

- **Support tool: Chatwoot vs Plain vs Intercom** — deferred. Per-feature feedback widget (above) covers the "collect user opinions on the product" need for now; help-desk ticketing can wait until there are actually customers with open questions. Draft picks + comparison tables + switch-triggers still live in [`/Users/yrish/.claude/plans/support-tool-and-n8n-decisions.md`](/Users/yrish/.claude/plans/support-tool-and-n8n-decisions.md) and [docs/support-software-research.md](support-software-research.md).
- **Automation hosting: n8n self-hosted (Compose) vs n8n Cloud** — deferred with the support-tool decision. Nothing in the current stack actively needs an event bus.

---

## Issues found in browser smoke (2026-04-20)

### Issue A: No dev path to simulate inbound email — **Landed 2026-04-21**

Shipped [`python manage.py simulate_inbound_email`](../backend/email_organiser/management/commands/simulate_inbound_email.py). Resolves a project by UUID or `generic_email`, creates the `IncomingEmail` row with a generated RFC-5322 message-id, and enqueues the same two Celery tasks the webhook fires (`create_incoming_email_notification`, `classify_incoming_email`). Supports `--skip-classify` when you don't want to burn Anthropic credits. Verified end-to-end — a simulated email lands in the DB and Celery picks it up.

Example:
```
docker compose exec backend python manage.py simulate_inbound_email \
  --project website-project@smithconsulting.com --subject "Delay on phase 2"
```

### Issue B: Nested routes under Projects all return 404 — **Fixed 2026-04-21**

**Root cause:** `invited_account` users were issued `InvitedAccount` rows by the legacy `/api/projects/<id>/invite/` endpoint but **never** a matching `ProjectMembership` row. Every permission check across `projects/`, `contracts/`, `chat/`, `email_organiser/`, and `notifications/` filters by `ProjectMembership` — so invited users got an empty list from `/api/projects/` and a 404 on `/api/projects/<id>/`. The 404 cascaded into every nested tab because the layout's `useProject(id)` query errored out and none of the tab endpoints authorised the request either.

Reproduced by logging in as `mike.invited@example.com` (fixture user, `invited_account` role) against `project 301`:
- `GET /api/projects/` → `count: 0`
- `GET /api/projects/33333333-3333-3333-3333-333333333301/` → `404`
- Every tab endpoint behind the same check → `403` or `404`

**Fix:**
1. [backend/email_organiser/views.py](../backend/email_organiser/views.py) `ProjectInviteView.post()` now mirrors every `InvitedAccount` creation into a `ProjectMembership.get_or_create(...)` so the legacy invite endpoint is symmetric with `ProjectMemberAddView` (the one the frontend actually uses).
2. [backend/fixtures/initial_data.json](../backend/fixtures/initial_data.json) gains a `projectmembership` row for `mike.invited` → project 301, backfilling the broken seed data so anyone running `loaddata` gets a working invited user.
3. [backend/tests/test_permissions.py](../backend/tests/test_permissions.py) adds `test_project_invite_endpoint_creates_projectmembership` pinning the behaviour: invite → user sees the project in their list and can hit detail.

Verified end-to-end: after reload, mike's project list returns the invited project and every nested tab endpoint returns 200.

**Deferred / not in this fix:** the wider question of whether `InvitedAccount` should exist as a separate model at all, now that every invite path also creates `ProjectMembership`. Captured as a cleanup candidate — a single-migration consolidation that drops `InvitedAccount` and its URL would remove a whole class of "which table says who's invited?" confusion.

---

## Program plans

## [research] User feedback program (Plan A + Plan C)

**Status:** adopted 2026-04-19. Details in [docs/research.md](research.md).  
**Phase 1:** landed 2026-04-20 (`1c99cc8`, `9e09848`).  
**Next:** Phase 2 (A.2) — app-wide feedback widget.

Phase 2 scope:
- `AppFeedback` model.
- Floating feedback button.
- Django admin triage view.
- n8n webhook integration.

Blocker: support-tool decision (Chatwoot vs Plain vs Intercom).

Program intent:
- Always-on in-app capture (AI thumbs + floating feedback).
- Structured research cadence (quarterly NPS + interview opt-in).
- Five phased slices; Phase 1 already delivered the first labeled dataset for email organiser evaluation.

## [support] Customer support surface + event bus

**Status:** adopted 2026-04-19. Details in [docs/support.md](support.md).

Current recommendation:
- Chatwoot (self-hosted) as conversation source of record.
- n8n as event bus to fan out feedback/support events to Slack, Notion, Linear, and PagerDuty.

Tooling choice must be finalized before first production rollout.

## [infra] Hosting + email provider choice

**Status:** options documented 2026-04-19. Details in [docs/hosting_plans.md](hosting_plans.md).

Three viable stacks:
- Fly.io + Postmark (lowest operational overhead).
- Scaleway + Brevo (EU residency focus).
- Hetzner + Postmark (lowest cost at scale).

Decision required before first production deploy. Current default recommendation: Fly.io + Postmark.

---

## Per-project manager scoping (tightening oversight)

**Status:** deferred from security finding #8. See [docs/security.md](security.md).

### Current model

Users with `role=MANAGER` currently have global visibility across all projects, contracts, and contract requests.

Examples:
- [backend/contracts/views.py](../backend/contracts/views.py): `ContractListCreateView`, `ContractDetailView`, `ContractActivateView`, `ContractRequestApproveView`, `ContractRequestRejectView`
- helper [`_user_can_read_project`](../backend/contracts/views.py)

### Proposed model

Managers should be scoped to explicitly assigned projects (via `ProjectMembership` or a new `ManagerAssignment` table). Cross-project access should require an elevated role.

This is important for future multi-company operation without full multi-tenant infrastructure. It keeps one Postgres and one backend process, while preventing cross-company visibility.

### Scope

1. **Data model**
   - Option A: extend `ProjectMembership` with a `role` column (`MANAGER` / `MEMBER`).
   - Option B: add `ManagerAssignment(user, project)`.
2. **Permissions**
   - Add `IsProjectManager` in [accounts/permissions.py](../backend/accounts/permissions.py).
   - Enforce both `role == MANAGER` and project assignment.
   - Replace direct `IsManager` use on write endpoints.
3. **Querysets**
   - Remove manager-global shortcuts like `if user.role == user.MANAGER: qs = qs.all()`.
   - Apply project scoping in `contracts/views.py`, `projects/views.py`, `email_organiser/views.py`, `notifications/views.py`, `dashboard/views.py`, and chat views.
4. **Super-admin path**
   - Add `SUPER_ADMIN` role (or `User.is_superuser`) for genuinely global workflows (billing, diagnostics, seed data).
5. **Frontend**
   - Update manager dashboards, project pickers, and any "all projects" UX to reflect scope.
6. **Tests**
   - Add explicit "manager A cannot see manager B project" coverage.
   - Include contract approval/activation and inbound webhook routing paths.
7. **Migration**
   - Backfill default assignments from existing managers to existing projects to preserve current behavior during rollout.

### Non-goals

- No database-per-tenant split.
- No per-tenant deployments.
- No subdomain-based tenant routing.
- Tenant remains derived from authenticated user context.

### Risks and mitigations

- **Risk:** missed view/task creates silent data leaks.  
  **Mitigation:** regression suite with two managers/two projects, asserting no cross-visibility on all list endpoints.
- **Risk:** single-tenant installations break during rollout.  
  **Mitigation:** feature flag `PROJECT_SCOPED_MANAGERS=True` (default off for first release).

### Related work

- Security finding #8 (currently accepted-risk, reopens when this lands).
- Inbound email routing currently uses `project.generic_email`; tenants need disjoint address pools or tenant-aware routing.

---

_Last updated: 2026-04-22 (per-feature feedback widget landed; support-tool decision postponed)._

# Future Implementation Plans

Long-horizon design work that isn't scheduled yet. Each item lists motivation, scope, and the files that would be touched so the ticket can be picked up cold.

---

## Issues surfaced 2026-04-20 (browser smoke after Phase 1)

Two things the user hit while clicking around with `FEATURE_AI_THUMBS=true`. Neither blocks the Security #5 next step, but both want a first-pass triage before more feature work lands.

### Issue A — No way to simulate inbound email in dev

Phase 1's AI-thumbs widget only renders once an email has been classified + analysed, and the inbound-email path isn't exercised end-to-end in dev because there's no live mailbox forwarding into the webhook. Today the only way to light up the classification + analysis + thumbs surface is to POST to [`/api/webhooks/inbound-email/`](../backend/email_organiser/views.py) directly with the right `X-Webhook-Secret`.

**Action for next session:** add a dev affordance — either a Django management command (`python manage.py simulate_inbound_email --project=<id> --subject=...`) that calls the same code path as the webhook, or a seeded fixture the dev stack loads on first boot. First option is cheaper and matches how the other email-pipeline tests construct emails ([`incoming_email_factory`](../backend/tests/conftest.py) in conftest).

### Issue B — Every nested feature under Projects tab 404s

Observed: clicking into a project → chat, contract, change request, timeline, invite — all return 404. Widespread enough that it's probably a single root cause (frontend route shape mismatch or a recent backend URL rename), not five separate bugs.

**Triage for next session:**

1. First, confirm this is **not** caused by today's work — Phase 1 only added `/api/feedback/ai/` and a `features` field on `/api/auth/me/`. Nothing in the patch touches project routing. Reproduce on a clean checkout of `377a29f` (pre-Phase-1) before assuming regression.
2. DevTools → Network: note the exact 404 URL for at least one feature (chat or contract is easiest). If it's the frontend Next.js route 404ing, the problem is on the frontend router. If the browser reaches the Django API and that 404s, the backend URL conf moved.
3. Suspect areas: the `development` branch was active earlier in the session (see git status at session start) and `main` is what we've been pushing to — if those diverged on project routes, a merge may have dropped URL patterns.
4. Also worth checking: the Next.js 16.2.2 startup log mentioned "The 'middleware' file convention is deprecated. Please use 'proxy' instead." That's a warning, not an error, but if frontend route resolution changed between Next 15 and 16, nested `[projectId]` routes may be affected.

Capture actual 404 URLs + a screenshot before diving into code.

---

## Next session — pick one

1. ~~**Phase 1 — AI-suggestion thumbs**~~ **Landed 2026-04-20** (commit `1c99cc8`). Delivered `POST /api/feedback/ai/`, `<AiFeedback>` widget on email classifications + suggested replies, `FEATURE_AI_THUMBS` flag exposed via `/api/auth/me/`. 13 feedback tests + 116 suite green. Also fixed 7 unrelated pre-existing test failures while the env was warm (commit `9e09848`). Next research phase (A.2 app-wide widget) is still queued per [research.md](research.md).
2. **Security #5 — HttpOnly refresh cookie + in-memory access token.** Planned 2026-04-20 with the user; implementation deferred. Scope is narrower than the original bullet said: CSP is already prod-enforced, so the work is purely the token-storage refactor. Multi-tab different-users support is being dropped as part of the fix. **Step-by-step plan + locked-in decisions in [docs/security_5_plan.md](security_5_plan.md).** Next session can pick this up cold.
3. **Open decisions** (unblocks the `[support]` plan entirely; also relevant to Phase 2 of research):
   - Chatwoot vs Plain vs Intercom.
   - n8n self-host (in compose) vs n8n Cloud.

---

## [research] User feedback program (Plan A + Plan C)

**Status:** adopted 2026-04-19 — detail in [docs/research.md](research.md).
**Phase 1 landed 2026-04-20** (commits `1c99cc8`, `9e09848`).
**Next up:** Phase 2 — app-wide feedback widget (A.2). `AppFeedback` model + floating button + triage view in Django admin + n8n webhook. Blocked on the support-tool decision (Chatwoot vs Plain vs Intercom) — see open decisions above.

Combines always-on in-app capture (AI-suggestion thumbs + floating feedback widget) with a structured research program (quarterly NPS, interview opt-in pipeline). Phased over 5 implementation slices; Phase 1 is the smallest and delivers a labelled evaluation dataset for the email organiser.

## [support] Customer support surface + event bus

**Status:** adopted 2026-04-19 — detail in [docs/support.md](support.md).

Chatwoot (self-hosted, default recommendation) as the single conversation system of record; n8n as the event bus that fans feedback/support events out to Slack, Notion, Linear, and PagerDuty. Tool choice flagged for decision before first production rollout.

## [infra] Hosting + email provider choice

**Status:** alternatives documented 2026-04-19 — detail in [docs/hosting_plans.md](hosting_plans.md).

Three coherent combos laid out (Fly.io + Postmark for minimal ops; Scaleway + Brevo for EU residency; Hetzner + Postmark for cheapest-at-scale). Decision owed before first production deploy; default recommendation is the Fly.io combo.

---

## Per-project manager scoping (tightening oversight)

**Status:** deferred — captured from security review finding #8 ([docs/security.md](security.md)).

**Today's model:** a user with `role=MANAGER` has *global* oversight of every project, contract, and contract-request. This is consistent across:
- [backend/contracts/views.py](../backend/contracts/views.py) — `ContractListCreateView`, `ContractDetailView`, `ContractActivateView`, `ContractRequestApproveView`, `ContractRequestRejectView`
- helper [`_user_can_read_project`](../backend/contracts/views.py) (added for finding #4)

**Proposed model:** managers are scoped to the projects they are explicitly assigned to (via `ProjectMembership` or a new `ManagerAssignment` table). Any cross-project action requires an elevated super-admin role.

**Why this matters beyond security:**

> This modification supports future expansion. For the creation of separate instances for multi company access.

Per-manager scoping is the precondition for hosting multiple customer companies (tenants) in the same deployment without building a full multi-tenant database layer. Each company's managers would see only their own projects, contracts, and email-organiser data, even though everyone shares one Postgres database and one backend process.

**Scope of the change:**

1. **Data model** — decide between:
   - reusing `ProjectMembership` rows with a new `role` column (`MANAGER`/`MEMBER`), or
   - a dedicated `ManagerAssignment(user, project)` table (cleaner when a manager's *type* is per-project, not per-user).
2. **Permissions layer** — extend [accounts/permissions.py](../backend/accounts/permissions.py) with a new `IsProjectManager` permission that checks both `role == MANAGER` *and* the membership table. Replace bare `IsManager` usage on write endpoints.
3. **Queryset filtering** — remove the `if user.role == user.MANAGER: qs = qs.all()` branches across `contracts/views.py`, `projects/views.py`, `email_organiser/views.py`, `notifications/views.py`, `dashboard/views.py`, and the chat app. Every list endpoint must filter by assigned projects.
4. **Super-admin escape hatch** — introduce a `SUPER_ADMIN` role (or a `User.is_superuser` gate) for the few legitimately global workflows: cross-company billing views, platform-wide diagnostics, seed-data management.
5. **Frontend** — manager dashboards, project pickers, and any "all projects" toggles need to respect the new scope. Most of the UI already fetches through the scoped endpoints, so backend filtering drives most of the behavior.
6. **Tests** — add explicit "manager A cannot see manager B's project" coverage, especially around the contract approval/activation flows and the email-organiser inbound webhook (which routes by the project's generic email address — tenants must not share that address space).
7. **Migration** — existing data assumes one tenant. For the rollout: create a default `ManagerAssignment` row linking every current manager to every current project, preserving behavior until tenants are introduced.

**Explicit non-goals for this change:**
- No database-per-tenant split. We stay on shared Postgres + shared Redis; isolation is enforced at the permission / queryset layer only.
- No separate deploys per tenant. One codebase, one backend, one frontend.
- No subdomain-based routing. Tenant is determined by the authenticated user.

**Risks:**
- Silent data leaks if any viewset or Celery task is missed during the sweep. Mitigation: add a regression test that spins up two managers in two projects and asserts zero cross-visibility across every list endpoint.
- Breaking existing single-tenant deployments. Mitigation: feature-flag the new scoping (`PROJECT_SCOPED_MANAGERS=True` default off) during the first release.

**Related findings / work:**
- Security finding #8 (closed in the changelog as accepted-risk under the current design; reopens when this plan lands).
- The email-organiser webhook already routes by `project.generic_email` — tenants must have disjoint address pools, or the router needs a tenant prefix.

---

_Last updated: 2026-04-20._

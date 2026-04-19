# Future Implementation Plans

Long-horizon design work that isn't scheduled yet. Each item lists motivation, scope, and the files that would be touched so the ticket can be picked up cold.

---

## Next session — pick one

1. **Phase 1 — AI-suggestion thumbs** (~3 days). Smallest implementation slice from the research program; delivers a labelled eval dataset for the email organiser. Scope detail in the `[research]` entry below.
2. **Security #5 — JWT + CSP hardening.** Parked during the security pass because it touches auth end-to-end. Move refresh tokens to `HttpOnly; SameSite=Strict` cookies, keep access tokens in memory, flip CSP from Report-Only to enforcing. See [docs/security.md](security.md#5).
3. **Open decisions** (unblocks #1 before it hits production scale, and unblocks the `[support]` plan entirely):
   - Chatwoot vs Plain vs Intercom.
   - n8n self-host (in compose) vs n8n Cloud.

---

## [research] User feedback program (Plan A + Plan C)

**Status:** adopted 2026-04-19 — detail in [docs/research.md](research.md).
**Next up:** Phase 1 — AI-suggestion thumbs (~3 days). New `feedback` Django app, `AISuggestionFeedback` model, `POST /api/feedback/ai/`, `<AiFeedback>` React component on classification and suggestion outputs. No consent UI needed for this slice (low-PII). Ship behind feature flag `feature.ai_thumbs`.

Combines always-on in-app capture (AI-suggestion thumbs + floating feedback widget) with a structured research program (quarterly NPS, interview opt-in pipeline). Phased over 5 implementation slices; Phase 1 is the smallest and delivers a labelled evaluation dataset for the email organiser.

## [support] Customer support surface + event bus

**Status:** adopted 2026-04-19 — detail in [docs/support.md](support.md).

Chatwoot (self-hosted, default recommendation) as the single conversation system of record; n8n as the event bus that fans feedback/support events out to Slack, Notion, Linear, and PagerDuty. Tool choice flagged for decision before first production rollout.

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

_Last updated: 2026-04-19._

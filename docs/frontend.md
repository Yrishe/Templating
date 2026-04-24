# Frontend

End-to-end reference for the Next.js frontend: what it does, how it's wired, and where each feature lives. Aimed at someone new to the codebase who needs to ship a change today.

## What it is

A Next.js 16 (App Router) SPA that backs the contract-management product. Users are **Managers** (platform oversight), **Accounts** (create projects, upload contracts), or **Invited Accounts** (limited members on someone else's project). Every project gets its own chat, contract, change-request lifecycle, timeline, and AI-assisted email organiser.

## Stack

| Layer | Tech |
|---|---|
| Framework | Next.js 16 (App Router, server + client components) |
| Language | TypeScript |
| Styling | Tailwind CSS + a small shadcn-style UI kit under [components/ui/](../frontend/src/components/ui/) |
| Server state | TanStack Query 5 (wrapped by [QueryProvider](../frontend/src/components/providers/query-provider.tsx)) |
| Client state | React context: [AuthProvider](../frontend/src/context/auth-context.tsx), [ThemeProvider](../frontend/src/context/theme-context.tsx) |
| Real-time | Native WebSocket against the Django Channels endpoint |
| Forms | `react-hook-form` + `zod` + `@hookform/resolvers` |
| Icons | `lucide-react` |
| HTTP | Custom `api` wrapper in [lib/api.ts](../frontend/src/lib/api.ts) (not fetch / axios directly) |
| Tests | Jest (unit) + MSW 2 (API mocks) + Playwright (e2e, scaffolded) |

## Directory map

```
frontend/src/
  app/
    (auth)/               # public routes (login, signup). No navbar/sidebar.
      login/
      signup/
    (app)/                # authenticated routes. Layout adds navbar + sidebar.
      dashboard/
      projects/
        new/              # create-project form
        [id]/             # project detail (route group with tabs)
          chat/
          contract/
          change-requests/
          timeline/
          invite/
      email-organiser/
        [projectId]/
      profile/
        [id]/
      settings/
  components/
    auth/                 # login + signup forms
    chat/                 # ChatWindow + MessageBubble
    contracts/            # contract view + change-request forms
    dashboard/            # notification feed, project summary card, pending-managers panel
    email-organiser/      # email list, analysis panel
    feedback/             # AiFeedback (phase 1), FeatureFeedback (phase 1.5)
    layout/               # navbar, sidebar
    projects/             # create form, project card
    providers/            # QueryProvider
    timeline/             # timeline view
    ui/                   # shadcn-style primitives (Button, Card, Dialog, Input, Tabs, …)
  context/                # AuthProvider, ThemeProvider
  hooks/                  # TanStack Query hook wrappers per domain
  lib/                    # api wrapper, ROUTES constants, utils (cn, formatDate)
  mocks/                  # MSW handlers for tests
  types/                  # domain types (User, Project, Contract, Notification, …)
```

## Auth model (Security #5)

Critical to understand before touching any authenticated request.

- **Refresh token** lives in an `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api/auth/`. JS cannot read it. XSS in a browser tab cannot exfiltrate it.
- **Access token** lives in a module-level ref in [lib/api.ts](../frontend/src/lib/api.ts) (`accessTokenStore`) — a plain JS heap variable. A reload clears it.
- **Bootstrap flow:** every page load starts with `accessTokenStore = null`. [AuthProvider](../frontend/src/context/auth-context.tsx) calls `tryRefreshToken()` on mount. That POSTs to `/api/auth/token/refresh/` with no body; the browser attaches the HttpOnly cookie. If the cookie is valid, the server returns a fresh access token and sets a rotated refresh cookie. The app then fetches `/api/auth/me/` to hydrate the user.
- **401 recovery:** the `api` wrapper detects a 401 response on any non-refresh call, calls `tryRefreshToken()` once, and retries. A shared in-flight promise guarantees one refresh at a time even if 20 tabs of components hit 401 simultaneously.
- **Logout:** POST `/api/auth/logout/` — server blacklists the refresh token and clears the cookie; client clears `accessTokenStore`.
- **Multi-tab different-users support was deliberately dropped.** Cookies are per-origin, so whichever tab logs in last wins. Concurrent sessions for different users require separate Chrome profiles / incognito.
- **WebSocket auth:** the refresh cookie is scoped to `/api/auth/` and doesn't ride on the WS upgrade. [useChat](../frontend/src/hooks/use-chat.ts) forwards the in-memory access token as `?token=<access>` on the WS URL.

Full design + rationale in [docs/security_5_plan.md](security_5_plan.md).

## Routing

Uses the App Router with two route groups:

- **`(auth)`** — [login](../frontend/src/app/\(auth\)/login/) + [signup](../frontend/src/app/\(auth\)/signup/). No navbar/sidebar. Unauthenticated users land here.
- **`(app)`** — every authenticated route. Layout wraps children with [navbar](../frontend/src/components/layout/navbar.tsx) + [sidebar](../frontend/src/components/layout/sidebar.tsx) + AuthProvider guard.

Named route constants in [lib/constants.ts:34](../frontend/src/lib/constants.ts#L34) — **always use `ROUTES.PROJECT(id)` etc., never hand-rolled template strings.** Keeps the routes in one place so rename is a single-edit.

## Features

### Authentication

**Login** ([app/(auth)/login/page.tsx](../frontend/src/app/\(auth\)/login/), form in [components/auth/](../frontend/src/components/auth/))
- Email + password. No "remember me" checkbox — refresh cookie max-age (24 h) is the session length.
- Submit → `api.post('/api/auth/login/')` → server sets refresh cookie + returns `{user, access}` → `accessTokenStore.set(access)` → redirect to `/dashboard`.

**Signup** ([app/(auth)/signup/page.tsx](../frontend/src/app/\(auth\)/signup/))
- `role` is either `account` or `manager`. `invited_account` is never self-selected — those come from a manager's invite.
- Manager signups land `is_active=false` pending approval. The form shows a "Your account needs admin approval" notice in that case.

**Pending manager approval** ([components/dashboard/pending-managers-panel.tsx](../frontend/src/components/dashboard/pending-managers-panel.tsx))
- Rendered on the dashboard **only for active managers** (see [use-auth.ts](../frontend/src/hooks/use-auth.ts) role check).
- Lists pending manager signups. Approve → PATCH to activate; reject → DELETE the pending user.

### Dashboard

[app/(app)/dashboard/](../frontend/src/app/\(app\)/dashboard/) — the post-login landing page.

Three quick-stat cards (projects, pending change requests, notifications) → recent notifications feed → grid of recent project summary cards. Manager-only: the Pending Managers panel shows above the feed when there are pending signups.

Powered by `useDashboard()` in [hooks/use-notifications.ts](../frontend/src/hooks/use-notifications.ts), which hits `/api/dashboard/` and gets the whole bundle in one call (count + recent_notifications + recent_projects).

### Projects

**List** ([app/(app)/projects/page.tsx](../frontend/src/app/\(app\)/projects/)) — renders every project the user can see via `useProjects()`. Grid of [ProjectCard](../frontend/src/components/projects/project-card.tsx).

**Create** ([app/(app)/projects/new/](../frontend/src/app/\(app\)/projects/new/), form in [create-project-form.tsx](../frontend/src/components/projects/create-project-form.tsx))
- Manager or Account users only. `owner_user_id` is a manager-only field (assigns the new project to another user).
- On success the server auto-provisions `generic_email`, Chat, Timeline, EmailOrganiser rows.

**Detail** ([app/(app)/projects/[id]/](../frontend/src/app/\(app\)/projects/[id]/))
- [layout.tsx](../frontend/src/app/\(app\)/projects/[id]/layout.tsx) holds the project name, a breadcrumb back to `/projects`, and the tab bar (pill-shaped, glass surface).
- **Overview** ([page.tsx](../frontend/src/app/\(app\)/projects/[id]/page.tsx)) — quick stats (member count, contract status, pending requests), notification feed scoped to the project, quick-link cards to each tab, project-details card. Bottom: `<FeatureFeedback>` widget.
- **Chat** (`chat/`) — real-time messaging via [useChat](../frontend/src/hooks/use-chat.ts). See the WebSocket section below.
- **Contract** (`contract/`) — view/upload/edit the project contract. PDF magic-byte + size gate. Contract status (draft/active/expired), text extraction badge (pypdf / textract / manual), download via [downloadAuthed()](../frontend/src/lib/api.ts) which fetches as a blob with `Authorization: Bearer` (needed because `<a href>` can't attach the header).
- **Change Requests** (`change-requests/`) — full history of change requests against the contract. Accounts can raise; managers approve/reject with a review comment. Approval of a draft contract auto-activates it server-side.
- **Timeline** (`timeline/`) — [TimelineView](../frontend/src/components/timeline/timeline-view.tsx) lists events with dates, priority, status. Create/edit limited to the project owner + managers. Comments on events support five comment types (`general`, `completion_confirmation`, `status_update`, `feedback`, `suggestion`).
- **Invite** (`invite/`) — search registered users by email/name, add them as a `ProjectMembership`. Gated to managers + the project's account owner (server enforces; frontend hides the form for anyone else).

### Real-time chat

[components/chat/chat-window.tsx](../frontend/src/components/chat/chat-window.tsx) + [hooks/use-chat.ts](../frontend/src/hooks/use-chat.ts).

- WS URL: `${WS_BASE_URL}/ws/chat/<projectId>/?token=<access>`.
- **Fallback polling:** REST `GET /api/chats/<projectId>/messages/` every 5 s, so chat keeps working when the WS connection is down (e.g. plain `runserver` without daphne).
- **Status indicator** in the chat header: `Connecting...` (spinner) → `Live` (green Wi-Fi) → `Polling` (grey Wi-Fi-off) when WS drops.
- **Reconnect with exponential backoff** up to 5 attempts. After that, polling only.
- **Send path:** if WS connected, send over WS. Else POST the message via REST and optimistically append.

### Email Organiser

[app/(app)/email-organiser/[projectId]/](../frontend/src/app/\(app\)/email-organiser/[projectId]/) — AI-assisted inbound email triage.

- [EmailOrganiserPanel](../frontend/src/components/email-organiser/email-organiser-panel.tsx) lists incoming emails grouped by category (delay, damage, scope_change, costs, delivery, compliance, quality, dispute, general, irrelevant) with relevance badges (high/medium/low/none). Filter by category / relevance / resolved / relevant flags.
- [AnalysisPanel](../frontend/src/components/email-organiser/analysis-panel.tsx) — detail view for a selected email. Shows AI-generated risk assessment, contract references, mitigation suggestions, suggested response, resolution path, timeline impact. Actions: **Resolve** (marks occurrence resolved), **Re-analyse** (re-runs the classification pipeline). Inline `<AiFeedback>` thumbs on both the classification and the suggested reply.
- Inbound emails enter via `POST /api/webhooks/inbound-email/` (HMAC-verified); a Celery task classifies + analyses. See `docs/email_organiser.md` for the backend pipeline.

### Notifications

[components/dashboard/notification-feed.tsx](../frontend/src/components/dashboard/notification-feed.tsx) + [hooks/use-notifications.ts](../frontend/src/hooks/use-notifications.ts).

- Per-project feed with 12 types (contract request, approved/rejected, contract update, chat message, new email, deadline upcoming, timeline comment, email high relevance, email occurrence unresolved, manager alert, system).
- **Actor-suppressed** — you never see your own actions.
- **Per-user dismissal** — marking as read dismisses only for the clicking user.
- Click-through deep-links to the relevant project tab.

### Feedback surfaces

**Phase 1 — AI thumbs** ([components/feedback/ai-feedback.tsx](../frontend/src/components/feedback/ai-feedback.tsx))
- Inline on AI outputs (email classifications, suggested replies). Compact thumbs-up / thumbs-down icons with an optional reason textarea that appears after a click.
- Rating POSTs immediately; comment debounces 3 s of idle before re-POSTing (backend upsert handles both).
- Gated on `features.ai_thumbs` from `/api/auth/me/`. Returns `null` when off.

**Phase 1.5 — per-feature feedback** ([components/feedback/feature-feedback.tsx](../frontend/src/components/feedback/feature-feedback.tsx))
- Card-sized widget mountable on any feature page. Props: `featureKey: string` (dotted, e.g. `dashboard.home`, `projects.overview`), optional `projectId`, optional `label`.
- Currently mounted on Dashboard, Project Overview, and the email-organiser analysis panel.
- Same upsert / debounce / silent-revert UX as Phase 1, but scoped to a feature key rather than an AI artefact.
- Gated on `features.feature_feedback`.

Phase 2 (global floating "Feedback" button + n8n fan-out) is sketched in [docs/research.md](research.md) but deferred.

### Settings

[app/(app)/settings/](../frontend/src/app/\(app\)/settings/) — theme selector (light / dark / system) driven by [ThemeProvider](../frontend/src/context/theme-context.tsx). Theme is stored in `localStorage` and applied by toggling a `.dark` class on `<html>`.

### Profile

[app/(app)/profile/[id]/](../frontend/src/app/\(app\)/profile/[id]/) — read-only profile page for any user the current user can see. Shows email, role, join date.

## Cross-cutting

### Feature flags

Tiny env-driven gates so a feature can be dark-launched and pulled without a redeploy. Pattern:

1. Backend `FEATURE_<NAME>` env var → exposed via `/api/auth/me/features.<name>` (see [accounts/serializers.py](../backend/accounts/serializers.py)).
2. Frontend [useFeatureFlag(name)](../frontend/src/hooks/use-feature-flag.ts) reads from `user.features` first, falls back to `NEXT_PUBLIC_FEATURE_<NAME>` build-time env for SSR / anonymous paths.
3. Components return `null` when the flag is off.

Current flags: `ai_thumbs`, `feature_feedback`.

### Theme

Three states — `light`, `dark`, `system` — controlled by [ThemeProvider](../frontend/src/context/theme-context.tsx). The `system` option subscribes to `prefers-color-scheme` and flips the `.dark` class live. No flash-of-wrong-theme because the initial class is set before hydration (inline script in the root layout).

### CSP + security headers

[middleware.ts](../frontend/src/middleware.ts) sets CSP on every response. Production enforces `script-src 'self'` (no `unsafe-inline`, no `unsafe-eval`) — dev runs Report-Only to keep Next.js HMR working. `connect-src` pulls from `NEXT_PUBLIC_API_URL` + `NEXT_PUBLIC_WS_URL` so the policy matches the actual backend origin. Also sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY`, `Permissions-Policy` (opts out of camera/mic/geolocation/FLoC), and `Strict-Transport-Security` in prod.

### API wrapper

[lib/api.ts](../frontend/src/lib/api.ts) is the single HTTP primitive — do not call `fetch` directly from components. It handles:

- Bearer token injection from `accessTokenStore`
- `credentials: 'include'` so the refresh cookie travels with `/api/auth/*` calls
- 401-retry via `tryRefreshToken()` with a single-flight guarantee
- Error body flattening (DRF-style `{field: ["msg"]}` → one `Error` message)
- `downloadAuthed(url)` for authenticated binary downloads (blob → object URL → trigger click)

### TanStack Query hooks

One hook per API surface, each exporting typed query/mutation helpers plus a `keys` object for cache invalidation. Files in [hooks/](../frontend/src/hooks/):

| Hook | Covers |
|---|---|
| [use-auth.ts](../frontend/src/hooks/use-auth.ts) | current user shortcut, derived from AuthContext |
| [use-projects.ts](../frontend/src/hooks/use-projects.ts) | projects, tags, memberships, contracts, contract requests, timeline + events + comments |
| [use-chat.ts](../frontend/src/hooks/use-chat.ts) | WebSocket connection state + send/receive (not TanStack — React state + ws ref) |
| [use-email-organiser.ts](../frontend/src/hooks/use-email-organiser.ts) | incoming emails, analysis, resolve, reanalyse |
| [use-notifications.ts](../frontend/src/hooks/use-notifications.ts) | notifications list, mark-read, dashboard bundle |
| [use-feedback.ts](../frontend/src/hooks/use-feedback.ts) | `useSubmitAiFeedback`, `useSubmitFeatureFeedback` |
| [use-feature-flag.ts](../frontend/src/hooks/use-feature-flag.ts) | read `/me.features.<key>` with SSR fallback |

### Error handling conventions

- 401 → `api` retries once with a fresh access token; if that also 401s, throw, let the caller show an error state.
- 403 / 404 → throw; the component renders an empty state ("You don't have access to this project", "Not found").
- Network / 500 → throw; components should show a "something went wrong, try again" UI. No global error boundary today; each component handles it inline.

## Environment variables

| Var | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Backend origin. Baked at build time into the JS bundle. |
| `NEXT_PUBLIC_WS_URL` | WebSocket origin (`wss://…` in prod). Build-time. |
| `NEXT_PUBLIC_FEATURE_AI_THUMBS` | SSR fallback for the feature flag. Build-time. |
| `NEXT_PUBLIC_FEATURE_FEATURE_FEEDBACK` | SSR fallback for the per-feature feedback flag. Build-time. |

Build-time gotcha: `NEXT_PUBLIC_*` values are substituted into the bundle by `next build`, not read at runtime. Changing them in prod requires a rebuild. [frontend/Dockerfile](../frontend/Dockerfile) declares matching `ARG` directives in the builder stage so CI / Render can pass them via docker build-args.

## Testing

| What | How |
|---|---|
| Unit | Jest + Testing Library. Component tests live under [src/__tests__/](../frontend/src/__tests__/). |
| API mocks | MSW 2 with handlers in [src/mocks/handlers.ts](../frontend/src/mocks/handlers.ts). |
| E2E | Playwright, scaffolded but not yet running in CI. |
| Type-check | `npm run type-check` → `tsc --noEmit`. Gates PR merges. |
| Lint | `npm run lint` → `next lint`. |

Run locally: `cd frontend && npm install --legacy-peer-deps && npm test`. The `--legacy-peer-deps` flag is load-bearing — `eslint-config-next@16` requires `eslint@>=9` but the lockfile pins `eslint@8`; strict resolution fails.

## Running locally

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev            # http://localhost:3000
```

Or via the root docker compose (recommended — runs the full backend + DB + Redis stack alongside):

```bash
docker compose up -d
# http://localhost:3000 for the frontend, http://localhost:8000/api/docs/ for the backend
```

See [RUNNING.md](../RUNNING.md) for the full first-run walkthrough including fixture loading and the bootstrap manager password reset.

## Known gaps / TODO

- **No global error boundary.** Individual components handle errors inline — a network failure in one card doesn't take the whole page down, but also means there's no consistent "oops, something went wrong" surface. Candidate for a shadcn-style `<Toast>` plus a root error boundary.
- **Playwright e2e tests are scaffolded but not running in CI.** The project has `@playwright/test` installed; add a `playwright` job to `.github/workflows/frontend-ci.yml`.
- **No form-level loading skeletons.** Most list endpoints have a simple "loading..." placeholder; replace with skeleton cards once design settles.
- **Chat doesn't virtualize long histories.** Currently re-renders every message on each poll. Fine up to ~500 messages; add `react-virtual` before the first long-running project.
- **No offline detection.** The chat polling fallback handles transient WS drops, but the app shows stale data silently if the whole network goes away. Low priority — show a banner when `navigator.onLine` flips.

## Pointers

- [README.md](../README.md) — project overview, stack table, role summary
- [docs/backend.md](backend.md) — backend features mirror (kept in sync)
- [docs/email_organiser.md](email_organiser.md) — AI pipeline detail
- [docs/security.md](security.md) + [docs/security_5_plan.md](security_5_plan.md) — security posture + auth-storage rationale
- [docs/research.md](research.md) — feedback + NPS + interview-opt-in program
- [docs/deploy_runbook.md](deploy_runbook.md) — production ops

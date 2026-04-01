# Scaffold & CI/CD Setup — Implementation Notes

This document explains every step taken to complete the Next.js frontend scaffold and CI/CD pipeline for the Contract Management Web Application.

---

## 1. Reviewed Existing Codebase

Before writing anything, the entire existing codebase was read to understand what was already in place:

- **`technical_specification.docx`** and **`project_plan.docx`** — confirmed the 4-stage roadmap, 17 domain entities, stack decisions (Next.js + Django + PostgreSQL + Redis), and the requirement to build the frontend against MSW mocks before the backend is ready.
- **`docker-compose.yml`** — already defined services for `postgres`, `redis`, `backend`, `celery`, `celery-beat`, and `frontend`, but had no frontend `Dockerfile` to build from.
- **`frontend/`** — components, hooks, context, types, and utilities were all written. What was missing was the Next.js App Router page tree (`src/app/`), the CSS variables, the MSW mock layer, and the test/build configuration files.
- **`.github/workflows/`** — `backend-ci.yml`, `frontend-ci.yml`, `security-scan.yml`, and `staging-deploy.yml` already existed and were well-written. What was missing was a production CD workflow and the staging CD did not yet build the frontend image.

---

## 2. CSS Variables & Global Styles (`src/app/globals.css`)

The existing `tailwind.config.ts` referenced CSS custom properties (`hsl(var(--primary))`, `hsl(var(--border))`, etc.) but there was no `globals.css` to define them. Without this file the app would render with broken colours.

`globals.css` was created with:
- `@tailwind base/components/utilities` directives so Tailwind generates its utility classes.
- A full set of `:root` CSS variables for every design token used across the UI components (background, foreground, primary, secondary, muted, accent, destructive, border, input, ring, radius).
- A `.dark` block with the same tokens mapped to dark-mode values, ready for a future dark-mode toggle.
- A `@layer base` block that applies `border-border` to all elements and `bg-background text-foreground` to `body`, which is the standard shadcn/ui baseline.

---

## 3. QueryClientProvider Wrapper (`src/components/providers/query-provider.tsx`)

Next.js App Router requires that anything using React state or hooks lives in a `'use client'` component. `QueryClient` from TanStack Query must be created inside a client component so it is not re-created on every server render.

A `QueryProvider` wrapper component was created that:
- Is marked `'use client'`.
- Creates a `QueryClient` instance inside `useState` so the same instance is reused across re-renders.
- Sets sensible defaults: `staleTime: 60s` (avoids redundant refetches) and `retry: 1`.
- Wraps children in `QueryClientProvider`.

---

## 4. Root Layout (`src/app/layout.tsx`)

The root layout is the entry point for the entire app. It was created to:
- Load the `Inter` Google Font and apply it to the `<body>`.
- Set `<html lang="en" suppressHydrationWarning>` to prevent React hydration warnings caused by browser extensions modifying the DOM.
- Define page `metadata` with a `template` so every page title renders as `"Page Name | ContractMgr"`.
- Wrap the entire app in `QueryProvider` (TanStack Query) and then `AuthProvider` (the existing auth context), so both are available everywhere without needing to be repeated on each page.

---

## 5. Root Page (`src/app/page.tsx`)

A minimal page that immediately calls Next.js `redirect()` to send unauthenticated and authenticated users alike to `/dashboard`. The `AuthGuard` on the dashboard layout then decides whether to continue or redirect to `/login`.

---

## 6. Auth Route Group (`src/app/(auth)/`)

Route groups (folder names in parentheses) let Next.js share a layout without adding a URL segment.

**`(auth)/layout.tsx`** — a centred, full-height layout with the ContractMgr logo above the form card. Used by both login and signup so both pages get the same chrome without repeating it.

**`(auth)/login/page.tsx`**:
- Client component with a `useForm` (react-hook-form) + `zodResolver` (Zod) form.
- Validates email format and non-empty password before submitting.
- Calls `useAuth().login()`, which hits `POST /api/auth/login/` and stores the returned user in context (the JWT is set as an httpOnly cookie by the backend).
- On success, redirects to `/dashboard`. On error, displays the server error message inline.
- If the user is already authenticated, redirects away immediately via a `useEffect`.

**`(auth)/signup/page.tsx`**:
- Same pattern as login, but collects first name, last name, email, password, and role.
- Role is restricted to `subscriber` or `invited_account` — managers are not self-service, matching the domain model.
- Uses a native `<select>` styled to match the design system rather than a third-party dropdown component, keeping dependencies minimal.

---

## 7. App Route Group (`src/app/(app)/`)

All authenticated pages live here. The layout wraps everything in `AuthGuard`, which redirects to `/login` if the user is not authenticated and to `/dashboard` if a user tries to access a page their role does not permit.

**`(app)/layout.tsx`** — renders `<Navbar>` at the top, `<Sidebar>` on the left (hidden on mobile), and a `<main>` content area. The sidebar is already role-aware: it hides the "New Project" link from invited accounts.

---

## 8. Dashboard Page (`src/app/(app)/dashboard/`)

Split into two files following the Next.js App Router pattern:
- `page.tsx` — a server component that sets the `<title>` via `metadata` and renders the client component.
- `dashboard-content.tsx` — the actual client component.

The dashboard calls `useDashboard()` which fetches `/api/dashboard/` and returns aggregated data in a single request. It renders:
- A greeting with the user's first name.
- Three stat cards: active project count, pending contract requests, and unread notifications.
- A 2-column grid: recent projects (using the existing `ProjectSummaryCard`) on the left, and the existing `NotificationFeed` on the right.
- A list of recent contract requests with colour-coded status badges.

---

## 9. Projects Pages (`src/app/(app)/projects/`)

**`projects/page.tsx` + `projects-content.tsx`** — lists all projects in a responsive grid using the existing `ProjectCard` component. Includes a search input that filters by project name client-side. Managers see a delete button on each card. Empty state shows a "Create your first project" prompt to eligible roles.

**`projects/new/page.tsx`** — wraps the existing `CreateProjectForm` in an `AuthGuard` that restricts access to managers and subscribers only. Invited accounts cannot reach this URL even if they navigate to it directly.

---

## 10. Project Nested Layout (`src/app/(app)/projects/[id]/layout.tsx`)

Projects have four sub-pages (Overview, Chat, Contract, Timeline). A nested layout was created so the project name header and tab bar are shared across all four without repeating them.

The layout:
- Reads the `id` param and calls `useProject(id)` to fetch the project name.
- Shows a "← All Projects" back link.
- Renders the project name (with a skeleton placeholder while loading).
- Renders a tab bar with four links. The active tab is determined by comparing `usePathname()` against each tab's href, and is highlighted with a bottom border in the primary colour.

---

## 11. Project Sub-Pages

Each sub-page follows the same two-file pattern (server `page.tsx` + client `*-content.tsx`) to enable `metadata` on server components while keeping the interactive parts client-only.

**`projects/[id]/page.tsx`** — the project overview. Shows four stat cards (member count, contract status, pending requests, project email), four quick-link cards that navigate to each section, a pending contract requests panel for managers, and a project details table.

**`projects/[id]/chat/page.tsx`** — renders the existing `ChatWindow` component, which fetches the chat object, loads historical messages, and opens a WebSocket connection via the existing `useChat` hook (with exponential-backoff reconnect).

**`projects/[id]/contract/page.tsx`** — renders the existing `ContractView` component. Managers additionally see a "New Contract" button that posts to `POST /api/contracts/`.

**`projects/[id]/timeline/page.tsx`** — renders the existing `TimelineView` component, which displays events sorted by start date on a vertical timeline. Managers can add events via an inline form.

**`email-organiser/[projectId]/page.tsx`** — renders the existing `EmailOrganiserPanel` (incoming emails) and `FinalResponseEditor` (draft and send replies) side by side.

---

## 12. MSW Mock Layer (`src/mocks/`)

The project plan specifies that the frontend must be testable against a mock API before the backend is built. MSW (Mock Service Worker) v2 was used because it intercepts real `fetch` calls at the network level, so the application code does not need any changes to run against mocks vs the real API.

Three files were created:

**`handlers.ts`** — defines `http` handlers for every API endpoint the frontend calls. Each handler returns realistic data shaped exactly like the real DRF responses (paginated `{ count, next, previous, results }` envelopes, correct field names, ISO timestamps). Handlers cover:
- Auth: login, logout, signup, me
- Dashboard aggregation
- Projects CRUD
- Contracts CRUD
- Contract requests (create, list, review)
- Notifications (list, mark read, mark all read)
- Project memberships
- Timeline events
- Chat and messages
- Emails
- Final responses and recipients

**`browser.ts`** — calls `setupWorker(...handlers)` for use in the browser during development (opt-in — not auto-started).

**`server.ts`** — calls `setupServer(...handlers)` for use in Jest (Node environment). The test setup starts and stops this server around each test suite.

---

## 13. Jest Configuration (`jest.config.ts` + `jest.setup.ts`)

**`jest.config.ts`**:
- Uses `next/jest` to pick up Next.js's Babel/SWC transform, path aliases, and environment handling automatically.
- Sets `testEnvironment: 'jsdom'` so React components can render in tests.
- Maps `@/*` to `src/*` so test files can use the same import aliases as the source.
- Excludes the `e2e/` folder (Playwright tests run separately).
- Sets a coverage threshold of **80%** across all four metrics (branches, functions, lines, statements), matching the project plan gate.
- Excludes generated files (`*.d.ts`), mocks, and Next.js page/layout entry points from coverage collection.

**`jest.setup.ts`**:
- Imports `@testing-library/jest-dom` so matchers like `toBeInTheDocument()` are available in every test file.
- Starts the MSW server before all tests, resets handlers after each test (prevents state leaking between tests), and stops the server when the suite finishes.

---

## 14. Playwright Configuration (`playwright.config.ts`)

- Runs tests from the `e2e/` directory.
- Fully parallel in development, single-worker in CI (avoids race conditions on shared CI runners).
- Retries failed tests twice in CI before marking them as failed.
- Tests against four browser projects: Chromium, Firefox, WebKit (Safari), and Mobile Chrome (Pixel 5).
- Uses `PLAYWRIGHT_BASE_URL` env var (defaults to `http://localhost:3000`) so the same config works in CI and locally.
- In development, automatically starts `npm run dev` as the web server before running tests.
- Captures screenshots on failure and full traces on first retry.

---

## 15. Frontend Dockerfile

A three-stage build:

1. **`deps`** — copies `package.json` and `package-lock.json` and runs `npm ci --frozen-lockfile`. Isolating this stage means Docker can cache the `node_modules` layer and skip re-installing unless the lock file changes.

2. **`builder`** — copies source and runs `npm run build`. `NEXT_TELEMETRY_DISABLED=1` is set to prevent Next.js from making network calls during the build. The build produces a `.next/standalone` directory (enabled by `output: 'standalone'` in `next.config.js`) which contains only the files needed to run the server, without the full `node_modules`.

3. **`runner`** — a lean production image. Creates a non-root `nextjs` user (UID 1001) for security. Copies only the standalone output and static assets from the builder. Exposes port 3000. The entrypoint is `node server.js` (the standalone Next.js server) rather than `npm start`, which avoids the npm process overhead.

`next.config.js` was updated to add `output: 'standalone'` to enable the standalone build mode that the Dockerfile depends on.

---

## 16. `package.json` — `type-check` Script

The existing scripts did not include a TypeScript type-check command. The frontend CI workflow calls `tsc --noEmit` to catch type errors without emitting files. A `"type-check": "tsc --noEmit"` script was added so the CI can call `npm run type-check` consistently.

---

## 17. CI/CD Workflows

### Pre-existing workflows (kept as-is)

| File | What it does |
|---|---|
| `backend-ci.yml` | lint (ruff), type-check (mypy), pytest ≥80% coverage, migration integrity check |
| `frontend-ci.yml` | ESLint, TypeScript check, Jest, Playwright E2E on push to main |
| `security-scan.yml` | Gitleaks secret scanning, pip-audit, npm audit on every push and PR |
| `staging-deploy.yml` | Builds and pushes backend Docker image to GHCR, deploys to staging, smoke tests |

### New workflows added

**`cd-staging.yml`** — triggered on every push to `main`. Builds and pushes both the backend and frontend Docker images to whichever registry is configured (`vars.REGISTRY_URL`). The frontend build injects `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` as build args. Both jobs run in parallel. A third `deploy-staging` job then runs after both images are pushed, using the GitHub `staging` environment. It has commented-out deployment blocks for both AWS ECS and GCP Cloud Run — uncomment the one that matches the chosen cloud provider. After deployment it runs a smoke test against `vars.STAGING_URL`.

**`cd-production.yml`** — triggered only when a semver git tag (`v1.2.3`) is pushed. The same parallel build-and-push pattern, but tags images with the semver version and `latest`. The deploy step uses the GitHub `production` environment, which must be configured in the repository settings with required reviewers. This enforces a manual approval gate before anything reaches production. After a successful deploy it runs smoke tests and then automatically creates a GitHub Release with auto-generated release notes.

Both CD workflows use:
- `concurrency` groups to prevent parallel deploys to the same environment.
- `docker/metadata-action` for consistent image tagging.
- GitHub layer caching (`cache-from/to: type=gha`) to speed up repeated builds.

---

## File Tree of New Files

```
Management/
├── .env.example                          updated (added CELERY_RESULT_BACKEND)
├── .gitignore                            updated (added playwright-report/, test-results/)
├── .github/
│   └── workflows/
│       ├── cd-staging.yml                NEW
│       └── cd-production.yml             NEW
└── frontend/
    ├── Dockerfile                        NEW
    ├── jest.config.ts                    NEW
    ├── jest.setup.ts                     NEW
    ├── next.config.js                    updated (added output: 'standalone')
    ├── package.json                      updated (added type-check script)
    ├── playwright.config.ts              NEW
    └── src/
        ├── app/
        │   ├── globals.css               NEW
        │   ├── layout.tsx                NEW
        │   ├── page.tsx                  NEW
        │   ├── (auth)/
        │   │   ├── layout.tsx            NEW
        │   │   ├── login/page.tsx        NEW
        │   │   └── signup/page.tsx       NEW
        │   └── (app)/
        │       ├── layout.tsx            NEW
        │       ├── dashboard/
        │       │   ├── page.tsx          NEW
        │       │   └── dashboard-content.tsx  NEW
        │       ├── projects/
        │       │   ├── page.tsx          NEW
        │       │   ├── projects-content.tsx   NEW
        │       │   ├── new/page.tsx      NEW
        │       │   └── [id]/
        │       │       ├── layout.tsx    NEW
        │       │       ├── page.tsx      NEW
        │       │       ├── chat/
        │       │       │   ├── page.tsx        NEW
        │       │       │   └── chat-content.tsx NEW
        │       │       ├── contract/
        │       │       │   ├── page.tsx        NEW
        │       │       │   └── contract-content.tsx NEW
        │       │       └── timeline/
        │       │           ├── page.tsx        NEW
        │       │           └── timeline-content.tsx NEW
        │       └── email-organiser/
        │           └── [projectId]/
        │               ├── page.tsx      NEW
        │               └── email-organiser-content.tsx NEW
        ├── components/
        │   └── providers/
        │       └── query-provider.tsx    NEW
        └── mocks/
            ├── handlers.ts               NEW
            ├── browser.ts                NEW
            └── server.ts                 NEW
```

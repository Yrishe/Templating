# Changelog

## [Unreleased] — 2026-04-10

### Fixed — Schema, auth, contract request scoping, membership endpoint

#### `/api/schema/` returns 500 — NoneType has no attribute 'method'
- `backend/contracts/views.py`: `ContractListCreateView.get_parsers()` and `ContractDetailView.get_parsers()` crashed when `self.request` was `None` during DRF schema introspection. Added `self.request is not None` guard in both methods.

#### Authenticated API requests return 401 Unauthorized
- `backend/accounts/authentication.py`: `CookieJWTAuthentication.authenticate()` returned `None` on expired/invalid cookie tokens instead of raising `InvalidToken`. DRF treated this as "no authentication attempted", silently downgrading the request to anonymous. Now raises `InvalidToken` so the client gets a proper 401.
- `frontend/src/lib/api.ts`: added automatic token refresh interceptor — on 401, calls `POST /api/auth/token/refresh/` and retries the original request once. Concurrent 401s share a single refresh call to avoid race conditions.

#### New projects show pending contract requests from other projects
- `backend/contracts/views.py`: `ContractRequestListCreateView.get_queryset()` ignored the `?project=` query param, returning all requests for the user regardless of project. Added project filtering when the param is present.
- `frontend/src/hooks/use-projects.ts`: `useContractRequests` had no `enabled` guard — could fire without a `projectId` and fetch everything. Added `enabled: Boolean(projectId)`.

#### `/api/project-memberships/` returns 404
- `backend/projects/views.py`: added `ProjectMembershipListView` (ListAPIView) — lists memberships filtered by `?project=`, scoped so non-managers only see projects they belong to.
- `backend/projects/urls.py`: registered `GET /api/project-memberships/`.

---

## [Unreleased] — 2026-04-09

### Added — Project collaboration, Email Organiser dynamic reply, chat HTTP fallback

#### Invite existing accounts on project creation
- `backend/accounts/views.py`: new `UserSearchView` (`GET /api/auth/users/search/?q=&role=`) — authenticated user search by name/email; excludes the requester; optional `role` filter (used by the manager owner picker to scope results to Account users).
- `backend/accounts/urls.py`: registered `users/search/`.
- `frontend/src/components/projects/create-project-form.tsx`: new "Invite team members" section with debounced search, multi-select chips, and a per-row toggle. After project creation, invited users are added via `POST /api/projects/<id>/members/` (best-effort, non-blocking).

#### Notifications moved into the project overview
- `frontend/src/app/(app)/dashboard/dashboard-content.tsx`: removed `NotificationFeed` from the dashboard layout.
- `frontend/src/app/(app)/projects/[id]/page.tsx`: `NotificationFeed` rendered on the project overview page.
- `backend/notifications/views.py`: `NotificationListView` now honours `?project=<id>` so the per-project feed only shows that project's notifications.
- `frontend/src/hooks/use-notifications.ts`: `useNotifications(projectId?)` passes the filter through and uses a project-scoped query key.
- `frontend/src/components/dashboard/notification-feed.tsx`: accepts an optional `projectId` prop.
- `frontend/src/hooks/use-projects.ts`: `useCreateProject` now invalidates `notifications` and `dashboard` query caches on success so a freshly-created project doesn't show stale entries from sibling projects.

#### Group chat — HTTP fallback so the chat is never blocked
- `backend/chat/views.py`: `MessageListView` is now `ListCreateAPIView` — `POST /api/chats/<project_id>/messages/` creates a message (defaulting `chat=`/`author=`), enqueues `create_chat_message_notification`, and best-effort broadcasts on the channel layer when one is configured. WebSocket remains the primary transport when daphne/Channels is available.
- `frontend/src/components/chat/chat-window.tsx`: rewritten to:
  - Poll `/api/chats/<id>/messages/` every 5 s as a WS-independent fallback.
  - Send via WebSocket when connected; otherwise POST over HTTP and append the result locally.
  - Stop disabling the input/send button on WS state — only while a send is in flight.
  - Replace the alarming "Disconnected" header with "Live" / "Connecting…" / "Polling".
  - Normalise the `author` field across REST (nested object) and WS (`author_id`/`author_email`) so message ownership and avatars work for both transports.
- `frontend/src/components/chat/message-bubble.tsx`: hardened initials/display name lookup so non-string `author` payloads no longer crash (`message.author.slice is not a function`).

#### Removed Project Email card
- `frontend/src/app/(app)/projects/[id]/page.tsx`: deleted the `Project Email` stat tile and the `Generic email` row from the Project Details card; stats grid trimmed from 4 to 3 columns.

#### Email Organiser — dynamic reply generation
- `backend/email_organiser/views.py`: new `GenerateReplyView` (`POST /api/projects/<project_id>/incoming-emails/<pk>/generate-reply/`) that runs `generate_suggested_reply` synchronously and returns the most recent `FinalResponse` for the incoming email so the UI can render it immediately.
- `backend/email_organiser/urls.py`: registered the generate-reply route.
- `frontend/src/components/email-organiser/email-organiser-panel.tsx`: emails are now selectable; supports `selectedEmailId` and `onSelectEmail` props with a highlighted row state.
- `frontend/src/components/email-organiser/reply-panel.tsx`: NEW FILE — auto-generates a Claude-drafted reply when an inbound email is selected, with Regenerate / Save Draft / Send actions backed by the existing final-response endpoints.
- `frontend/src/app/(app)/email-organiser/[projectId]/email-organiser-content.tsx`: replaced the static `FinalResponseEditor` with the new master/detail flow (`EmailOrganiserPanel` ↔ `ReplyPanel`).

### Changed — Managers can create projects, tag deletion, contract page UX

#### Managers can create (and assign) projects
- `backend/projects/views.py`: `ProjectListCreateView.perform_create` now allows both `account` and `manager` roles. Managers may pass `owner_user_id` to assign the project to another active user; without it the project is owned by the creator. The Account row for the chosen owner is `get_or_create`'d, and both creator and (if different) owner are added as `ProjectMembership` rows so the chat group includes everyone.
- `frontend/src/hooks/use-projects.ts`: `CreateProjectPayload` widened to accept `owner_user_id`.
- `frontend/src/components/projects/create-project-form.tsx`: when the current user is a manager, a new "Project Owner" section appears with *Assign to me* / *Assign to an Account* buttons and a search picker (filtered to Account-role users) for the latter case.

#### Tags / priority labels can be deleted
- `backend/projects/views.py`: `TagDetailView` no longer restricts `DELETE` to managers — any authenticated user may delete a tag.
- `frontend/src/hooks/use-projects.ts`: new `useDeleteTag()` hook (`DELETE /api/tags/<id>/`).
- `frontend/src/components/projects/create-project-form.tsx`: each tag chip now has a small ✕ button (separate from the toggle) that confirms and deletes the tag, also clearing it from `selectedTagIds`.

#### Contract page on a freshly created project
- `backend/contracts/views.py`: `ContractListCreateView.get_queryset` now honours `?project=<id>` so the per-project Contract page no longer surfaces another project's contract on a brand-new project.
- `frontend/src/components/contracts/contract-view.tsx`: managers (not just accounts) can see and use the upload form, since managers can now create projects and need to upload the initial contract themselves.

---

## [Unreleased] — 2026-04-07

### Added

#### Phase 3 — inbound email, PDF text extraction & Claude-grounded suggestion replies

##### Inbound email pipeline (item 8)
- `backend/email_organiser/models.py`: new `IncomingEmail` model — `id` (uuid), `project` FK, `sender_email`/`sender_name`, `subject`, `body_plain`/`body_html`, `message_id` (unique — used to dedupe webhook deliveries), `received_at`, `raw_payload` (JSONField for forensics), `is_processed` flag, `created_at`. Indexed on `project` and `received_at`.
- `backend/email_organiser/serializers.py`: added `IncomingEmailSerializer` with all fields read-only-ish (id/created_at)
- `backend/email_organiser/views.py`: added `IncomingEmailListView` (project members can list inbound mail for a project) and `InboundEmailWebhookView` — a public, AllowAny POST endpoint that authenticates via the `X-Webhook-Secret` header against `settings.INBOUND_EMAIL_WEBHOOK_SECRET`. Looks up the project by `to` matching `Project.generic_email` (case-insensitive), dedupes by `message_id`, then enqueues `generate_suggested_reply.delay(...)`. Provider-agnostic JSON shape — adapters per provider (SES Inbound / SendGrid / Postmark) can be added later by mapping their fields onto the same body.
- `backend/email_organiser/urls.py`: registered `GET /api/projects/<uuid:project_id>/incoming-emails/` and `POST /api/webhooks/inbound-email/`
- `backend/config/settings/base.py`: added `INBOUND_EMAIL_WEBHOOK_SECRET` env var (required for the webhook to accept any request)
- `.env.example`: documented `INBOUND_EMAIL_WEBHOOK_SECRET` placeholder
- `docs/INBOUND_EMAIL_SETUP.md`: full setup guide — provider comparison table (SES Inbound recommended), step-by-step AWS SES + SNS → webhook wiring, MX record format, SNS signature verification notes for production hardening, manual `curl` recipe for testing without a real provider
- `frontend/src/types/index.ts`: added `IncomingEmail` interface
- `frontend/src/components/email-organiser/email-organiser-panel.tsx`: rewired the existing "Incoming Emails" panel from the legacy `/api/emails/?project=` endpoint to the new `/api/projects/<id>/incoming-emails/` route; uses the `IncomingEmail` type, displays sender name, subject, processed badge ("AI replied"), and expandable body
- `frontend/src/mocks/handlers.ts`: added mock handlers for the new incoming-emails list endpoint and the inbound webhook (the legacy `/api/emails/` handler is kept for any old test fixtures)

##### PDF text extraction (item 9)
- `backend/requirements/base.txt`: added `pypdf==4.2.0`
- `backend/contracts/tasks.py`: NEW FILE — `extract_contract_text(contract_id)` Celery task that loads `Contract.file`, runs `pypdf.PdfReader`, joins page texts, and stores the result in `Contract.content`. Gracefully handles missing files, missing `pypdf` dependency, and the empty-text case (logs a warning that the PDF is probably scanned/image-only — the user can paste plain text manually as a fallback)
- `backend/contracts/views.py`: `ContractListCreateView.perform_create` and `ContractDetailView.perform_update` now enqueue `extract_contract_text.delay(contract_id)` whenever a file is present, so contract text is ready for Claude's RAG context as soon as the file is uploaded

##### Claude-grounded suggestion replies (item 10)
- `backend/requirements/base.txt`: added `anthropic==0.30.0`
- `backend/config/settings/base.py`: added `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` settings (defaults to `claude-sonnet-4-6`)
- `.env.example`: documented `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`
- `backend/email_organiser/tasks.py`: NEW FILE — `generate_suggested_reply(incoming_email_id)` Celery task. **Narrowed-knowledge RAG approach**: instead of a vector index, the task pulls the project's contract text via the OneToOne relation and passes it as Claude's system prompt. Uses two prompt templates (`SYSTEM_PROMPT_TEMPLATE`, `USER_PROMPT_TEMPLATE`) that explicitly instruct Claude to use the contract as the only source of truth and to flag missing-from-contract questions rather than inventing terms. Caps context at 50k chars (contract) + 20k chars (incoming email body) to stay within Claude's safe input range. Persists the result as a `FinalResponse` with `status='suggested'`, `is_ai_generated=True`, `source_incoming_email` set, and a "Re: " subject prefix. Marks `IncomingEmail.is_processed = True` on success.
- **Graceful degradation**: if `ANTHROPIC_API_KEY` is unset OR the `anthropic` SDK is not installed, the task logs a warning and creates a placeholder draft (`[AI suggestion unavailable — please draft a reply manually.]` + the original message snippet). On API errors, it retries up to 2× before falling back to the placeholder.
- `backend/email_organiser/models.py`: `FinalResponse` gains `source_incoming_email` FK (nullable, on_delete=SET_NULL, related_name=`suggested_replies`) and `is_ai_generated: bool`. Added new status choice `SUGGESTED = "suggested"` ("AI Suggested") alongside the existing `DRAFT` and `SENT`.
- `backend/email_organiser/serializers.py`: `FinalResponseSerializer` exposes `source_incoming_email`, `is_ai_generated` (both read-only)
- `backend/email_organiser/migrations/0002_incoming_email_and_ai_suggestions.py`: schema migration creating `IncomingEmail`, adding `source_incoming_email` + `is_ai_generated` to `FinalResponse`, and updating the status choice list
- `frontend/src/types/index.ts`: `FinalResponseStatus` union extended with `'suggested'`; `FinalResponse` interface gains `source_incoming_email` (string | null) and `is_ai_generated: boolean`

##### Phase 3 — Key things to know (deployment / operational notes)
- **Two new Python dependencies**: run `pip install -r backend/requirements/base.txt` to pull in `pypdf==4.2.0` and `anthropic==0.30.0`
- **One Django migration to apply**: `python manage.py migrate email_organiser 0002` — creates `IncomingEmail`, adds `source_incoming_email` + `is_ai_generated` to `FinalResponse`, updates the status choice list
- **Two new env vars**:
  - `INBOUND_EMAIL_WEBHOOK_SECRET=<long random string>` — **required**; the webhook returns 401 without it
  - `ANTHROPIC_API_KEY=sk-ant-...` — *optional*; if unset the suggestion task creates a placeholder draft instead of calling Claude
  - `ANTHROPIC_MODEL` — defaults to `claude-sonnet-4-6`
- **End-to-end flow once wired up**: client emails `proj-<uuid8>@inbound.contractmgr.app` → SES Inbound (or chosen provider) → SNS / webhook POST → `/api/webhooks/inbound-email/` → `IncomingEmail` row → `generate_suggested_reply.delay(...)` → Claude reads `project.contract.content` + the incoming body → drafts a reply → `FinalResponse(status='suggested', is_ai_generated=True, source_incoming_email=<id>)` saved → user reviews / edits / sends via the existing Email Organiser panel
- **Narrowed-knowledge RAG approach (no vector DB)**: the project's full contract text (capped at 50 000 chars) is passed as Claude's system prompt on every call. Simpler than embeddings + retrieval and tightly scoped per project. If contracts ever exceed 50k chars or cross-contract reasoning is needed, swap in a chunking + retrieval strategy — the task is the only place that has to change.
- **Webhook is provider-agnostic**: SES Inbound, SendGrid Inbound Parse, Postmark, and Mailgun all work. The view expects the generic JSON shape documented in `docs/INBOUND_EMAIL_SETUP.md`. Provider-specific adapters (e.g. SNS signature verification, SendGrid's multipart format) can be added by swapping the auth block in `InboundEmailWebhookView.post`.
- **PDF text extraction is best-effort**: `pypdf` handles digital PDFs (~95% of contracts) trivially. Scanned/image-only PDFs return empty text — the task logs a warning and skips, leaving `Contract.content` empty. Users can paste plain text manually, or a follow-up can add OCR via `ocrmypdf` / Tesseract.
- **Graceful degradation everywhere**: `extract_contract_text` works even if `pypdf` is missing (logs a warning and exits cleanly); `generate_suggested_reply` works even if `anthropic` is missing or `ANTHROPIC_API_KEY` is unset (creates a placeholder draft so the inbound flow still completes end-to-end); the inbound webhook works even if the suggestion task fails to enqueue (logs the exception, returns 201 for the IncomingEmail).
- **Update `PROJECT_INBOUND_DOMAIN`** in `backend/projects/views.py` to your real verified subdomain when going live. Existing projects keep their old `generic_email`; only newly created projects pick up the new domain.
- **Manual test recipe** (no real provider needed):
  ```bash
  curl -X POST http://localhost:8000/api/webhooks/inbound-email/ \
    -H "Content-Type: application/json" \
    -H "X-Webhook-Secret: $INBOUND_EMAIL_WEBHOOK_SECRET" \
    -d '{"from":"test@example.com","to":"proj-12345678@inbound.contractmgr.app","subject":"Q","body_plain":"...","message_id":"<t1@x>","received_at":"2026-04-07T12:00:00Z"}'
  ```
- **All 26 frontend tests still pass**, TypeScript clean

##### Phase 3 — Deliberately deferred (call out before going live)
- **No SES-specific adapter yet** — the webhook accepts the generic JSON shape but does not parse the actual SES → SNS notification format or verify SNS signatures. Add `boto3` + the SNS message validator before exposing the endpoint to the public internet.
- **No OCR fallback** — scanned PDFs silently return empty `Contract.content`. Add `ocrmypdf` if image-only contracts become common.
- **No "AI Suggested" visual badge** in `FinalResponseEditor` — the data (`is_ai_generated`, `source_incoming_email`) is on every response payload but the editor doesn't yet visually distinguish AI drafts from human drafts. Small UX follow-up.
- **No backend tests for the new tasks/views** — the webhook, PDF extraction, and Claude suggestion task ship without unit tests because they involve external services (SES, pypdf, Anthropic) that need careful mocking. Worth adding once the deployment story is settled.

#### Phase 2 — projects: tags, status, manager-approves-manager workflow

##### Project status & "Completed Projects" stat (item 2)
- `backend/projects/models.py`: added `Project.STATUS_CHOICES` (`active` / `completed` / `archived`) with default `active`, plus a DB index on `status`
- `backend/projects/migrations/0002_tag_project_status_project_tags.py`: schema migration adding the `status` column, the index, the new `Tag` table, and the `Project.tags` M2M
- `backend/dashboard/views.py`: dashboard payload now exposes `completed_projects` (count of project member rows where `status='completed'`); `recent_projects` is filtered to active projects only
- `backend/dashboard/serializers.py`: added `completed_projects` and `pending_manager_count` fields
- `frontend/src/types/index.ts`: added `ProjectStatus` union and `Project.status`; added `completed_projects` + `pending_manager_count` to `DashboardData`
- `frontend/src/app/(app)/dashboard/dashboard-content.tsx`: replaced the "Unread Notifications" stat card with a green "Completed Projects" card sourced from `data.completed_projects` (item 7 + item 2 in one swap)

##### Free-form Tag model with colours (item 6)
- `backend/projects/models.py`: new `Tag` model — `id` (uuid), `name` (unique, max 64), `color` (hex string, default `#6B7280`), `created_by` FK, `created_at`; `Project.tags` is a M2M to `Tag`
- `backend/projects/serializers.py`: added `TagSerializer`; `ProjectSerializer` now exposes nested `tags` (read-only) and accepts a write-only `tag_ids` PrimaryKeyRelatedField for assignment on create/update
- `backend/projects/views.py`: added `TagListCreateView` (any authenticated user can list/create) and `TagDetailView` (delete restricted to managers)
- `backend/projects/urls.py`: registered `GET/POST /api/tags/` and `GET/DELETE /api/tags/<uuid:pk>/`
- `frontend/src/types/index.ts`: added `Tag` interface and `Project.tags: Tag[]`
- `frontend/src/hooks/use-projects.ts`: added `useTags()`, `useCreateTag()`, and `tagKeys`; `useCreateProject` payload type now accepts `tag_ids`
- `frontend/src/components/projects/create-project-form.tsx`: added an inline tag selector — existing tags render as toggleable chips; a name input + native colour picker creates new tags inline; selected tag IDs are submitted via `tag_ids`
- `frontend/src/components/projects/project-card.tsx`: project cards now render tag pills using each tag's colour for border, text, and a 15%-opacity background fill

##### Auto-generated project email (item 4)
- `backend/projects/models.py`: kept `generic_email` column but it is now considered server-controlled
- `backend/projects/serializers.py`: `generic_email` moved to `read_only_fields` — no longer accepted from client input
- `backend/projects/views.py`: `ProjectListCreateView.perform_create` now generates `proj-<first-8-of-uuid>@inbound.contractmgr.app` immediately after the project is saved; introduced `PROJECT_INBOUND_DOMAIN` constant (placeholder until SES Inbound is wired up in Phase 3)
- `frontend/src/components/projects/create-project-form.tsx`: removed the manual `generic_email` form field and its zod validation; description in the card explains the address is auto-generated

##### Manager-approves-Manager workflow (item 1)
- `backend/accounts/views.py`: added `_IsActiveManager` permission class and three new views — `PendingManagerListView` (GET pending manager signups), `PendingManagerApproveView` (POST `/<uuid:pk>/approve/` flips `is_active=True`), `PendingManagerRejectView` (POST `/<uuid:pk>/reject/` deletes the user record)
- `backend/accounts/urls.py`: registered `GET /api/auth/pending-managers/`, `POST /api/auth/pending-managers/<uuid:pk>/approve/`, `POST /api/auth/pending-managers/<uuid:pk>/reject/`
- `backend/dashboard/views.py`: managers' dashboard payload now includes `pending_manager_count` (count of `is_active=False` manager rows)
- `frontend/src/components/dashboard/pending-managers-panel.tsx`: new component — lists pending manager requests in a yellow-tinted card with inline Approve / Reject buttons; uses `usePendingManagers`, `useApprovePendingManager`, `useRejectPendingManager` (defined locally in the same file); polls every 60 s
- `frontend/src/app/(app)/dashboard/dashboard-content.tsx`: renders `<PendingManagersPanel />` above the stats grid for users with `role === 'manager'`

##### Restrict project invites to registered users (item 5)
- `backend/projects/serializers.py`: `ProjectMembershipSerializer` now accepts an optional `email` field alongside `user_id`; `validate()` rejects requests missing both; `create()` looks up the user by `user_id` or by case-insensitive `email`, raising a `ValidationError` ("No registered user found with this email address.") if no match — invitations to non-existent users are now impossible
- `backend/projects/views.py`: docstring on `ProjectMemberAddView` clarifies the new constraint; the view itself delegates validation to the serializer

#### Mock handlers — extended for the new endpoints
- `frontend/src/mocks/handlers.ts`: added `mockTags`; updated `mockProjects` with `status` and `tags` fields plus the new auto-generated email format; replaced the old `/api/dashboard/` payload with the new shape (matches `DashboardData` exactly); added `GET/POST /api/tags/`, `DELETE /api/tags/:id/`, and pending-manager endpoints

---

#### Notifications — new types & dashboard filter (Phase 1 of multi-phase notifications work)
- `backend/notifications/models.py`: added `CHAT_MESSAGE` and `CONTRACT_UPDATE` to `Notification.TYPE_CHOICES`
- `backend/notifications/migrations/0002_add_chat_and_contract_update_types.py`: alters `Notification.type` field choices
- `backend/notifications/tasks.py`: added two new Celery tasks — `create_chat_message_notification(message_id)` and `create_contract_update_notification(contract_id, action)`
- `backend/chat/consumers.py`: `_save_message` now fires `create_chat_message_notification.delay(...)` after persisting a new message
- `backend/contracts/views.py`: `ContractListCreateView.perform_create`, `ContractDetailView.perform_update`, and `ContractActivateView.post` all fire `create_contract_update_notification.delay(...)` with the appropriate action label (`created` / `updated` / `activated`)
- `frontend/src/types/index.ts`: extended `NotificationType` union with `'contract_update'` and `'chat_message'`
- `frontend/src/components/dashboard/notification-feed.tsx`: added `MessageSquare` (green) and `FilePen` (purple) icons + label rows for the two new types; introduced `PROJECT_FOCUSED_TYPES` constant and a frontend filter so the dashboard feed only shows `contract_request` / `contract_update` / `chat_message` — `system` and `manager_alert` continue to appear in the navbar bell dropdown for users who want the full feed
- `frontend/src/components/layout/navbar.tsx`: extended `getNotificationLabel` with `'contract update'` and `'new message'` strings
- `frontend/src/__tests__/components/dashboard/notification-feed.test.tsx`: added 3 new tests (chat_message rendering, contract_update rendering, all-filtered empty-state) and updated 3 existing tests that previously asserted `system` notifications appeared in the dashboard — now 26 tests pass, all green

#### Unit tests — notifications & settings (23 tests, all passing)
- `frontend/src/__tests__/components/dashboard/notification-feed.test.tsx`: 12 tests covering loading skeleton, error state, empty state, type-label rendering, unread badge logic, "Mark all read" button visibility + API call, individual mark-read button + API call, and icon colour
- `frontend/src/__tests__/pages/settings.test.tsx`: 11 tests covering heading, name pre-population, read-only email, role badge, save button, PATCH `/api/auth/me/` payload, success message, `refreshUser` invocation, error message, disabled-while-saving, and empty-name guard
- `frontend/src/__tests__/test-utils.tsx`: shared `renderWithQuery` helper + `mockUser` fixture
- `frontend/src/__tests__/jest-dom.d.ts`: type reference enabling `@testing-library/jest-dom` matchers in TypeScript

#### Profile page — view-only stub
- `frontend/src/app/(app)/profile/[id]/page.tsx`: Next.js dynamic route receiving `params.id`
- `frontend/src/app/(app)/profile/[id]/profile-content.tsx`: full UI shell — large avatar with disabled camera/upload button, name, role badge, status dot, "About" card (placeholder bio), "Details" card (email, member since, role), 3 placeholder activity stat cards (Projects / Contracts / Messages), and a "Profile not available" fallback for non-self IDs (shown until a `GET /api/users/:id/` endpoint is added)
- `frontend/src/components/layout/navbar.tsx`: "Profile" dropdown link now points to `/profile/${user.id}` instead of `/settings`
- **Functionality intentionally not activated** — photo upload, bio editing, status changes, and viewing other users' profiles are stubbed pending further confirmation

### Fixed

#### Test infrastructure — Jest/MSW setup unblocked
- `frontend/jest.config.ts` → `jest.config.js`: removed TypeScript config (no `ts-node` installed); also fixed the `setupFilesAfterFramework` typo (correct key is `setupFilesAfterEnv`) so `jest.setup.ts` actually loads
- `frontend/jest.config.js`: switched `testEnvironment` to `jest-fixed-jsdom` (jsdom does not expose Fetch API globals required by MSW v2)
- `frontend/jest.config.js`: override `transformIgnorePatterns` AFTER `next/jest` resolves the config — next/jest's defaults blocked transforming MSW's ESM-only deps (`msw`, `@mswjs`, `until-async`, `@bundled-es-modules`, `headers-polyfill`, `outvariant`, `strict-event-emitter`, `@open-draft`)
- `frontend/jest.setup.ts`: switched to `require()` (instead of `import`) so MSW server import is no longer hoisted ahead of polyfill setup
- `frontend/src/mocks/handlers.ts`: added `POST /api/notifications/:id/read/` handler — the existing `PATCH /:id/` handler did not match the URL `useMarkNotificationRead` actually calls
- Upgraded `jest-environment-jsdom` from 27 → 29 (was incompatible with `jest@29`)
- Installed dev deps: `@testing-library/dom` (peer dep of `@testing-library/react@16`), `@types/jest`, `undici`, `jest-fixed-jsdom`, `jest-environment-jsdom@29`

---

### Changed

#### Sidebar & navbar UX polish
- `frontend/src/components/layout/sidebar.tsx`: replaced confusing `ChevronLeft`/`ChevronRight` collapse toggle with `PanelLeftClose`/`PanelLeftOpen` icons — now visually distinct from nav-item indicators; removed the `ChevronRight` active-state arrow from each nav item (the primary-coloured highlight is sufficient)
- `frontend/src/components/layout/navbar.tsx`: added 300 ms close delay to both `NotificationDropdown` and `ProfileDropdown` — implemented via a `closeTimer` ref that is cleared on `onMouseEnter`, preventing accidental dismissal when the cursor moves from trigger to panel

---

### Fixed

#### Signup returns 400 / user not authenticated after login
- `backend/accounts/serializers.py`: removed `password2` confirm-password field from `UserRegistrationSerializer` — the signup form never sent it, causing every signup attempt to fail validation
- `frontend/src/context/auth-context.tsx`: fixed `login()` and `signup()` — both now treat the API response directly as `User` instead of reading `response.user` (which was always `undefined` because the backend returns the user profile at the root level, not nested under a `user` key)
- `frontend/src/lib/api.ts`: improved error handler to surface DRF field-level validation errors (e.g. "password: This password is too common.") instead of a bare "HTTP 400"
- `frontend/src/context/auth-context.tsx`: removed stale `AuthResponse` import

---

## [Unreleased] — 2026-04-06

### Changed — User Journey implementation

#### Role rename: `subscriber` → `account`
- `backend/accounts/models.py`: renamed `SUBSCRIBER = "subscriber"` → `ACCOUNT = "account"`; kept `SUBSCRIBER` as a backward-compat alias on the class
- `backend/accounts/migrations/0002_rename_subscriber_role.py`: alters field choices + data migration to update existing `"subscriber"` rows to `"account"`
- `frontend/src/types/index.ts`: `UserRole` updated to `'manager' | 'account' | 'invited_account'`
- `frontend/src/lib/constants.ts`: added `USER_ROLES.ACCOUNT = 'account'`; kept `USER_ROLES.SUBSCRIBER` as alias
- `frontend/src/app/(app)/dashboard/dashboard-content.tsx`: replaced `'subscriber'` role checks with `'account'`
- `frontend/src/app/(app)/projects/projects-content.tsx`: same — `canCreate` now checks `'account'` only

#### Contract PDF upload
- `backend/contracts/models.py`: added `file = FileField(upload_to='contracts/')`, made `content` optional (`blank=True`)
- `backend/contracts/migrations/0002_contract_pdf_file.py`: schema migration for new `file` column
- `backend/contracts/serializers.py`: added `file` field and `file_url` (absolute URL via `build_absolute_uri`)
- `backend/contracts/views.py`: added multipart parser support (`MultiPartParser`, `FormParser`) so PDF files can be uploaded via POST/PATCH
- `frontend/src/types/index.ts`: `Contract` interface gains `file: string | null` and `file_url: string | null`
- `frontend/src/lib/api.ts`: added `postForm` and `patchForm` methods; `Content-Type` header auto-omitted when body is `FormData`
- `frontend/src/hooks/use-projects.ts`: `useCreateContract` and `useUpdateContract` now accept `FormData | Partial<Contract>`; added `useActivateContract`

#### Contract ownership — Accounts create, Managers approve
- `backend/contracts/views.py`: Account users can now create contracts (previously Manager-only)
- `backend/projects/serializers.py`: `account` field is now read-only (auto-assigned server-side)
- `backend/projects/views.py`:
  - `perform_create` enforces Account-only project creation; auto-assigns or creates the user's `Account` profile; also auto-provisions `EmailOrganiser` on project creation
  - Managers now receive all projects in `GET /api/projects/` (team overview), not just their memberships
- `frontend/src/components/layout/sidebar.tsx`: "New Project" link restricted to `account` role only

#### Contract Request flow
- `backend/contracts/views.py`: `ContractRequestListCreateView.perform_create` fires a manager notification immediately when a request is submitted
- `backend/contracts/views.py`: `ContractRequestApproveView` now auto-activates the project's contract when a request is approved
- `frontend/src/hooks/use-projects.ts`: removed broken `useReviewContractRequest` (was PATCH to wrong endpoint); replaced with `useApproveContractRequest` and `useRejectContractRequest` (correct dedicated POST endpoints)
- `frontend/src/components/contracts/contract-view.tsx`: full rewrite — Account sees PDF upload form + contract request submission with status tracking; Manager sees PDF download link + approve/reject panel
- `frontend/src/app/(app)/projects/[id]/contract/contract-content.tsx`: simplified (logic moved into `ContractView`)

#### Manager role approval gate
- `backend/accounts/serializers.py`: `validate_role` blocks Invited Account self-registration; Manager signups set `is_active = False` pending Django admin approval
- `frontend/src/app/(auth)/signup/page.tsx`: Manager option added with approval warning notice; shows a "pending approval" screen after manager signup; Invited Account removed from self-registration
- `frontend/src/types/index.ts`: `User` gains `is_active: boolean`

#### Media file serving (development)
- `backend/config/urls.py`: added `static(MEDIA_URL, document_root=MEDIA_ROOT)` for serving uploaded files in development

#### Mock updates
- `frontend/src/mocks/handlers.ts`: default mock user switched to `account` role; contracts include `file`/`file_url` fields; POST `/api/contracts/:id/activate/` endpoint added; POST approve/reject endpoints added; contract create/update handlers support multipart form data

#### Diagram — User Journey page
- `Diagram.drawio`: added **Page 2 "User Journey"** — three colour-coded swimlanes (Account, Manager, Invited Account) with step boxes, decision diamonds, and cross-lane annotations showing the end-to-end flow

---

## [Unreleased] — 2026-04-03

### Fixed

#### Dashboard — "Recent Projects" not displaying
- Updated `DashboardData` type in `frontend/src/types/index.ts` to match actual backend response fields (`recent_projects`, `recent_notifications`, `pending_contract_requests`, etc.)
- Fixed `frontend/src/app/(app)/dashboard/dashboard-content.tsx` to read `data?.recent_projects` and `data?.recent_notifications` instead of the wrong `data?.projects` / `data?.notifications`
- Replaced broken `recentRequests` array (never returned by backend) with `data?.pending_contract_requests` count from the API

#### Timeline — failing to load
- Fixed `useProjectTimeline` in `frontend/src/hooks/use-projects.ts` to call `GET /api/projects/${projectId}/timeline/` (the correct backend endpoint) instead of the non-existent `GET /api/timeline-events/?project=`
- Fixed `useCreateTimelineEvent` to POST to `GET /api/projects/${projectId}/timeline/events/` and accept `projectId` alongside event data
- Added `Timeline` interface to `frontend/src/types/index.ts`
- Fixed `frontend/src/components/timeline/timeline-view.tsx` to read `data?.events` instead of `data?.results`, and renamed `timelineId` prop to `projectId` in `AddEventForm`

#### Settings page — read-only / blank
- Replaced static display in `frontend/src/app/(app)/settings/settings-content.tsx` with an editable form (first name, last name) that calls `PATCH /api/auth/me/`
- Email and role fields remain read-only
- Fixed blank page caused by a stale Turbopack compilation (empty module chunk) from a prior merge conflict in `(app)/layout.tsx` — resolved by clearing `.next` cache and restarting the dev server

#### Notifications — "Mark All Read" returns 404 / single mark-read broken
- Added `NotificationMarkAllReadView` to `backend/notifications/views.py`
- Registered `POST /api/notifications/mark-all-read/` in `backend/notifications/urls.py`
- Fixed `useMarkNotificationRead` in `frontend/src/hooks/use-notifications.ts` to call `POST /api/notifications/${id}/read/` instead of `PATCH /api/notifications/${id}/`

#### Build error — merge conflict markers in layout
- Resolved merge conflict in `frontend/src/app/(app)/layout.tsx` (`MobileSidebar` import conflict); kept `Sidebar`-only import since `MobileSidebar` is already used inside `Navbar`

### Notes

- **Task 1 (Manager role not set)** — requires a one-time Django shell command per affected account; no code change needed:
  ```bash
  python manage.py shell -c "
  from accounts.models import User
  u = User.objects.get(email='your@email.com')
  u.role = 'manager'
  u.save()
  "
  ```

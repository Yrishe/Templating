# Changelog

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

# Changelog

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

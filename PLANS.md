# Development Plans

## Next session

---

### 1. Manager account does not display "Create Project" option

**Root cause:**
A user created via `createsuperuser` has no `role` field set. The sidebar filters the "New Project" item by `[USER_ROLES.MANAGER, USER_ROLES.SUBSCRIBER]` — if `user.role` is `null` or `undefined`, the filter silently hides it.

**Fix:**
Set the role on the account via the Django shell:
```bash
python manage.py shell -c "
from accounts.models import User
u = User.objects.get(email='your@email.com')
u.role = 'manager'
u.save()
"
```
No frontend code change needed — the filtering logic is correct.

---

### 2. "Recent Projects" in Dashboard page does not display existing projects

**Root cause:**
Field name mismatch between backend and frontend. The backend (`dashboard/views.py`) returns:
```json
{ "recent_projects": [...], "recent_notifications": [...] }
```
But the frontend (`dashboard-content.tsx:20-22`) reads:
```ts
const projects = data?.projects ?? []
const notifications = data?.notifications ?? []
const recentRequests = data?.recent_contract_requests ?? []
```
None of those keys exist in the API response, so all three default to empty arrays.

**Fix:**
Update `dashboard-content.tsx` to use the correct field names from the API:
```ts
const projects = data?.recent_projects ?? []
const notifications = data?.recent_notifications ?? []
```
Note: `recent_contract_requests` is not returned by the backend at all — either add it to `DashboardView` or remove the related UI block.

**Files to change:**
- `frontend/src/app/(app)/dashboard/dashboard-content.tsx` — fix field names
- `backend/dashboard/views.py` — optionally add `recent_contract_requests` to the payload

---

### 3. Timeline failing to load

**Root cause:**
Two issues:
1. The frontend calls `GET /api/timeline-events/?project=${projectId}` but the backend needs to be verified as having this endpoint and filtering by `project` query param correctly.
2. The `TimelineEvent` type expects a `timeline` field (the timeline object ID), not a `project` ID directly — there may be a mismatch in how events are queried vs how they relate to projects.

**Fix:**
- Verify `GET /api/timeline-events/?project=<id>` returns results in the backend.
- If the backend filters by `timeline` (not `project`), first fetch the project's timeline object, then query events by `timeline` ID.
- Check `start_date` / `end_date` are returned as ISO strings the frontend can parse with `new Date()`.

**Files to check:**
- `backend/projects/views.py` or `backend/projects/urls.py` — confirm timeline-events endpoint exists and filters correctly
- `frontend/src/hooks/use-projects.ts:156` — `useProjectTimeline` hook
- `frontend/src/components/timeline/timeline-view.tsx` — rendering logic

---

### 4. Settings page not working

**Root cause:**
The settings page (`settings-content.tsx`) is read-only — it only displays the user's name, email, and role as static text. There are no form inputs or save actions, so the user cannot change anything.

**Fix:**
Replace the static display with an editable form:
- First name, last name: text inputs with a save button calling `PATCH /api/auth/me/` (or equivalent profile update endpoint)
- Email: read-only (email changes are sensitive and typically require re-verification)
- Role: read-only (role is assigned by an admin, not self-service)
- Add success/error feedback on save

**Files to change:**
- `frontend/src/app/(app)/settings/settings-content.tsx` — add form with react-hook-form + zod
- Verify backend has a `PATCH /api/auth/me/` endpoint for profile updates

---

### 5. Notifications "Mark All Read" returns 404

**Root cause:**
Two separate endpoint mismatches:

**Mark all read:** Frontend calls `POST /api/notifications/mark-all-read/` (`use-notifications.ts:41`) but this endpoint does not exist in the backend — `notifications/urls.py` only defines `notifications/`, `notifications/<uuid:pk>/read/`, and `notifications/emails/`.

**Mark single read:** Frontend calls `PATCH /api/notifications/${id}/` but the backend expects `POST /api/notifications/<uuid:pk>/read/`.

**Fix (backend):**
1. Add `mark-all-read` endpoint to `notifications/views.py`:
```python
class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from projects.models import ProjectMembership
        member_project_ids = ProjectMembership.objects.filter(
            user=request.user
        ).values_list("project_id", flat=True)
        Notification.objects.filter(
            project__in=member_project_ids, is_read=False
        ).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
```
2. Register it in `notifications/urls.py`:
```python
path("notifications/mark-all-read/", NotificationMarkAllReadView.as_view(), name="notification-mark-all-read"),
```
3. Fix single mark-read: either change the frontend to call `POST /api/notifications/${id}/read/` or add a `PATCH` handler to the backend — pick one and be consistent.

**Files to change:**
- `backend/notifications/views.py` — add `NotificationMarkAllReadView`
- `backend/notifications/urls.py` — register the new endpoint
- `frontend/src/hooks/use-notifications.ts:31` — fix `useMarkNotificationRead` to use `POST .../read/` instead of `PATCH .../`

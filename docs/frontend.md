# Frontend Features

> Template. One section per feature. Delete the "Template" section once you add your first real entry.

Stack: Next.js 16 (App Router), TypeScript, Tailwind CSS, Jest (unit), Playwright (e2e). Entry point: [frontend/src/](../frontend/src/).

---

## Feature: {{feature name}}

**Status:** {{proposed | in-progress | shipped}}
**Owner:** {{name}}
**Related backend feature:** {{link to docs/backend.md section, if any}}

### Summary
One or two sentences describing what the user can do.

### User-facing surface
- Route(s): `/path`
- Components: `src/components/.../Foo.tsx`
- Hooks / stores: `src/hooks/useFoo.ts`, `src/stores/foo.ts`

### API contracts consumed
| Endpoint | Method | Notes |
|---|---|---|
| `/api/...` | GET | ... |

### State & caching
- Server state: TanStack Query key `['foo', id]`, stale time N seconds
- Client state: ...

### Auth / permissions
Which roles can see or act on this feature, and how the frontend gates it (route guard, component guard, API error handling).

### Telemetry
Events fired, names, properties.

### Tests
- Unit: `src/components/.../Foo.test.tsx`
- Playwright: `tests/e2e/foo.spec.ts`

### Known gaps / TODO
- [ ] ...

---

## Feature: (next one)

import { http, HttpResponse } from 'msw'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

const mockUser = {
  id: 'user-1',
  email: 'account@example.com',
  first_name: 'Alice',
  last_name: 'Account',
  role: 'account' as const,
  is_active: true,
}

const mockManager = {
  id: 'user-2',
  email: 'manager@example.com',
  first_name: 'Bob',
  last_name: 'Manager',
  role: 'manager' as const,
  is_active: true,
}

const mockProjects = [
  {
    id: 'proj-1',
    account: 'acc-1',
    name: 'Q3 Vendor Agreement',
    description: 'Annual vendor contract renewal',
    generic_email: 'vendor-q3@example.com',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-03-20T14:00:00Z',
  },
  {
    id: 'proj-2',
    account: 'acc-1',
    name: 'Software Licence',
    description: 'Enterprise software licensing agreement',
    generic_email: 'sw-licence@example.com',
    created_at: '2026-02-01T09:00:00Z',
    updated_at: '2026-03-28T11:00:00Z',
  },
]

const mockContracts = [
  {
    id: 'contract-1',
    project: 'proj-1',
    title: 'Vendor Agreement 2026',
    file: null,
    file_url: null,
    content: '',
    status: 'active' as const,
    created_by: 'user-1',
    created_at: '2026-01-20T10:00:00Z',
    updated_at: '2026-02-10T10:00:00Z',
    activated_at: '2026-02-10T10:00:00Z',
  },
]

const mockNotifications = [
  {
    id: 'notif-1',
    project: 'proj-1',
    type: 'contract_request' as const,
    is_read: false,
    triggered_by_contract_request: 'req-1',
    triggered_by_manager: null,
    created_at: '2026-03-30T12:00:00Z',
  },
  {
    id: 'notif-2',
    project: 'proj-2',
    type: 'system' as const,
    is_read: true,
    triggered_by_contract_request: null,
    triggered_by_manager: null,
    created_at: '2026-03-29T09:00:00Z',
  },
]

const mockContractRequests = [
  {
    id: 'req-1',
    account: 'acc-2',
    project: 'proj-1',
    description: 'Request to review and approve updated terms',
    status: 'pending' as const,
    created_at: '2026-03-30T11:00:00Z',
    reviewed_at: null,
    reviewed_by: null,
  },
]

const paginate = <T>(items: T[]) => ({
  count: items.length,
  next: null,
  previous: null,
  results: items,
})

export const handlers = [
  // ── Auth ────────────────────────────────────────────────────────────────
  http.post(`${API}/api/auth/login/`, async ({ request }) => {
    const body = await request.json() as { email: string; password: string }
    if (body.password === 'wrong') {
      return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
    }
    return HttpResponse.json({ user: mockUser, access: 'mock-token', refresh: 'mock-refresh' })
  }),

  http.post(`${API}/api/auth/logout/`, () => {
    return new HttpResponse(null, { status: 204 })
  }),

  http.post(`${API}/api/auth/signup/`, async ({ request }) => {
    const body = await request.json() as Record<string, string>
    const user = { ...mockUser, ...body, id: 'user-new', role: body.role as typeof mockUser.role }
    return HttpResponse.json({ user, access: 'mock-token', refresh: 'mock-refresh' }, { status: 201 })
  }),

  http.get(`${API}/api/auth/me/`, () => {
    return HttpResponse.json(mockUser)
  }),

  // ── Dashboard ───────────────────────────────────────────────────────────
  http.get(`${API}/api/dashboard/`, () => {
    return HttpResponse.json({
      user: mockUser,
      notifications: mockNotifications,
      projects: mockProjects,
      recent_contract_requests: mockContractRequests,
    })
  }),

  // ── Projects ────────────────────────────────────────────────────────────
  http.get(`${API}/api/projects/`, () => {
    return HttpResponse.json(paginate(mockProjects))
  }),

  http.get(`${API}/api/projects/:id/`, ({ params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json(project)
  }),

  http.post(`${API}/api/projects/`, async ({ request }) => {
    const body = await request.json() as Record<string, string>
    const project = {
      id: `proj-${Date.now()}`,
      account: 'acc-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ...body,
    }
    return HttpResponse.json(project, { status: 201 })
  }),

  http.patch(`${API}/api/projects/:id/`, async ({ request, params }) => {
    const project = mockProjects.find((p) => p.id === params.id)
    if (!project) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const body = await request.json() as Record<string, string>
    return HttpResponse.json({ ...project, ...body, updated_at: new Date().toISOString() })
  }),

  http.delete(`${API}/api/projects/:id/`, () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // ── Contracts ───────────────────────────────────────────────────────────
  http.get(`${API}/api/contracts/`, ({ request }) => {
    const url = new URL(request.url)
    const projectId = url.searchParams.get('project')
    const filtered = projectId ? mockContracts.filter((c) => c.project === projectId) : mockContracts
    return HttpResponse.json(paginate(filtered))
  }),

  http.post(`${API}/api/contracts/`, async ({ request }) => {
    const contentType = request.headers.get('content-type') ?? ''
    let body: Record<string, string> = {}
    if (contentType.includes('multipart')) {
      const formData = await request.formData()
      formData.forEach((v, k) => { if (typeof v === 'string') body[k] = v })
    } else {
      body = await request.json() as Record<string, string>
    }
    const contract = {
      id: `contract-${Date.now()}`,
      file: null,
      file_url: null,
      content: '',
      created_by: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      activated_at: null,
      status: 'draft',
      ...body,
    }
    return HttpResponse.json(contract, { status: 201 })
  }),

  http.patch(`${API}/api/contracts/:id/`, async ({ request, params }) => {
    const contract = mockContracts.find((c) => c.id === params.id)
    if (!contract) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const contentType = request.headers.get('content-type') ?? ''
    let body: Record<string, unknown> = {}
    if (contentType.includes('multipart')) {
      const formData = await request.formData()
      formData.forEach((v, k) => { if (typeof v === 'string') body[k] = v })
    } else {
      body = await request.json() as Record<string, unknown>
    }
    return HttpResponse.json({ ...contract, ...body, updated_at: new Date().toISOString() })
  }),

  http.post(`${API}/api/contracts/:id/activate/`, ({ params }) => {
    const contract = mockContracts.find((c) => c.id === params.id)
    if (!contract) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json({ ...contract, status: 'active', activated_at: new Date().toISOString() })
  }),

  // ── Contract Requests ───────────────────────────────────────────────────
  http.get(`${API}/api/contract-requests/`, ({ request }) => {
    const url = new URL(request.url)
    const projectId = url.searchParams.get('project')
    const filtered = projectId
      ? mockContractRequests.filter((r) => r.project === projectId)
      : mockContractRequests
    return HttpResponse.json(paginate(filtered))
  }),

  http.post(`${API}/api/contract-requests/`, async ({ request }) => {
    const body = await request.json() as Record<string, string>
    const req = {
      id: `req-${Date.now()}`,
      status: 'pending',
      created_at: new Date().toISOString(),
      reviewed_at: null,
      reviewed_by: null,
      ...body,
    }
    return HttpResponse.json(req, { status: 201 })
  }),

  http.patch(`${API}/api/contract-requests/:id/`, async ({ request, params }) => {
    const req = mockContractRequests.find((r) => r.id === params.id)
    if (!req) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ ...req, ...body })
  }),

  http.post(`${API}/api/contract-requests/:id/approve/`, ({ params }) => {
    const req = mockContractRequests.find((r) => r.id === params.id)
    if (!req) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json({ ...req, status: 'approved', reviewed_at: new Date().toISOString(), reviewed_by: 'user-2' })
  }),

  http.post(`${API}/api/contract-requests/:id/reject/`, ({ params }) => {
    const req = mockContractRequests.find((r) => r.id === params.id)
    if (!req) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    return HttpResponse.json({ ...req, status: 'rejected', reviewed_at: new Date().toISOString(), reviewed_by: 'user-2' })
  }),

  // ── Notifications ────────────────────────────────────────────────────────
  http.get(`${API}/api/notifications/`, ({ request }) => {
    const url = new URL(request.url)
    const unreadOnly = url.searchParams.get('is_read') === 'false'
    const filtered = unreadOnly
      ? mockNotifications.filter((n) => !n.is_read)
      : mockNotifications
    return HttpResponse.json(paginate(filtered))
  }),

  http.patch(`${API}/api/notifications/:id/`, async ({ request, params }) => {
    const notif = mockNotifications.find((n) => n.id === params.id)
    if (!notif) return HttpResponse.json({ detail: 'Not found' }, { status: 404 })
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ ...notif, ...body })
  }),

  http.post(`${API}/api/notifications/mark-all-read/`, () => {
    return new HttpResponse(null, { status: 204 })
  }),

  // ── Project Memberships ─────────────────────────────────────────────────
  http.get(`${API}/api/project-memberships/`, () => {
    return HttpResponse.json(paginate([{ project: 'proj-1', user: 'user-1', joined_at: '2026-01-15T10:00:00Z' }]))
  }),

  // ── Timeline Events ─────────────────────────────────────────────────────
  http.get(`${API}/api/timeline-events/`, () => {
    return HttpResponse.json(paginate([
      {
        id: 'event-1',
        timeline: 'proj-1',
        title: 'Kick-off meeting',
        description: 'Initial project kick-off',
        start_date: '2026-01-15',
        end_date: null,
        status: 'completed',
        created_at: '2026-01-10T10:00:00Z',
      },
    ]))
  }),

  http.post(`${API}/api/timeline-events/`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `event-${Date.now()}`,
      created_at: new Date().toISOString(),
      ...body,
    }, { status: 201 })
  }),

  // ── Chat ────────────────────────────────────────────────────────────────
  http.get(`${API}/api/chats/`, ({ request }) => {
    const url = new URL(request.url)
    const projectId = url.searchParams.get('project')
    return HttpResponse.json(paginate([{ id: `chat-${projectId}`, project: projectId, created_at: '2026-01-15T10:00:00Z' }]))
  }),

  http.get(`${API}/api/messages/`, () => {
    return HttpResponse.json(paginate([]))
  }),

  // ── Emails ──────────────────────────────────────────────────────────────
  http.get(`${API}/api/emails/`, () => {
    return HttpResponse.json(paginate([]))
  }),

  // ── Final Responses ─────────────────────────────────────────────────────
  http.get(`${API}/api/final-responses/`, () => {
    return HttpResponse.json(paginate([]))
  }),

  http.post(`${API}/api/final-responses/`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({
      id: `response-${Date.now()}`,
      edited_by: null,
      sent_at: null,
      created_at: new Date().toISOString(),
      ...body,
    }, { status: 201 })
  }),

  http.patch(`${API}/api/final-responses/:id/`, async ({ request, params }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ id: params.id, ...body })
  }),

  // ── Recipients ──────────────────────────────────────────────────────────
  http.get(`${API}/api/recipients/`, () => {
    return HttpResponse.json(paginate([]))
  }),

  http.post(`${API}/api/recipients/`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>
    return HttpResponse.json({ id: `recipient-${Date.now()}`, ...body }, { status: 201 })
  }),
]

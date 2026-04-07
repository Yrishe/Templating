import React from 'react'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { NotificationFeed } from '@/components/dashboard/notification-feed'
import { renderWithQuery } from '../../test-utils'

// ─── helpers ────────────────────────────────────────────────────────────────

const paginate = <T,>(items: T[]) => ({
  count: items.length,
  next: null,
  previous: null,
  results: items,
})

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ─── tests ──────────────────────────────────────────────────────────────────

describe('NotificationFeed', () => {
  // ── loading state ──────────────────────────────────────────────────────────
  it('shows loading skeletons while fetching', () => {
    renderWithQuery(<NotificationFeed />)
    // The loading branch renders three animate-pulse skeleton divs
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  // ── error state ───────────────────────────────────────────────────────────
  it('shows an error message when the API call fails', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText(/failed to load notifications/i)).toBeInTheDocument()
    })
  })

  // ── empty state ───────────────────────────────────────────────────────────
  it('shows empty-state message when there are no notifications', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(paginate([]))
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })
  })

  // ── populated state ───────────────────────────────────────────────────────
  it('renders project-focused notification types and filters out system / manager_alert', async () => {
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      // mockNotifications contains one 'contract_request' and one 'system'
      // Only contract_request is project-focused, system is hidden by the filter
      expect(screen.getByText('Contract Request')).toBeInTheDocument()
    })
    expect(screen.queryByText('System')).not.toBeInTheDocument()
  })

  it('renders chat_message notifications with the "New Message" label', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(
          paginate([
            {
              id: 'msg-1',
              project: 'proj-1',
              type: 'chat_message',
              is_read: false,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-04-01T10:00:00Z',
            },
          ])
        )
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument()
    })
  })

  it('renders contract_update notifications with the "Contract Update" label', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(
          paginate([
            {
              id: 'upd-1',
              project: 'proj-1',
              type: 'contract_update',
              is_read: false,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-04-01T11:00:00Z',
            },
          ])
        )
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('Contract Update')).toBeInTheDocument()
    })
  })

  it('shows the empty state when only system / manager_alert notifications exist (all filtered)', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(
          paginate([
            {
              id: 'sys-1',
              project: 'proj-1',
              type: 'system',
              is_read: false,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-04-01T10:00:00Z',
            },
            {
              id: 'mgr-1',
              project: 'proj-1',
              type: 'manager_alert',
              is_read: false,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-04-01T11:00:00Z',
            },
          ])
        )
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText(/no notifications/i)).toBeInTheDocument()
    })
  })

  it('displays the unread count badge with the correct number', async () => {
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      // mockNotifications has 1 unread item (notif-1)
      expect(screen.getByText('1')).toBeInTheDocument()
    })
  })

  it('does not show the unread badge when all notifications are read', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(
          paginate([
            {
              id: 'notif-read',
              project: 'proj-1',
              type: 'contract_update',
              is_read: true,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-03-29T09:00:00Z',
            },
          ])
        )
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('Contract Update')).toBeInTheDocument()
    })
    // No destructive badge should be rendered
    expect(screen.queryByText('1')).not.toBeInTheDocument()
  })

  // ── mark all read ─────────────────────────────────────────────────────────
  it('shows the "Mark all read" button when there are unread notifications', async () => {
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /mark all read/i })
      ).toBeInTheDocument()
    })
  })

  it('hides the "Mark all read" button when all notifications are read', async () => {
    server.use(
      http.get(`${API}/api/notifications/`, () =>
        HttpResponse.json(
          paginate([
            {
              id: 'notif-all-read',
              project: 'proj-1',
              type: 'chat_message',
              is_read: true,
              triggered_by_contract_request: null,
              triggered_by_manager: null,
              created_at: '2026-03-29T09:00:00Z',
            },
          ])
        )
      )
    )
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: /mark all read/i })
    ).not.toBeInTheDocument()
  })

  it('calls the mark-all-read API when the button is clicked', async () => {
    let markAllCalled = false
    server.use(
      http.post(`${API}/api/notifications/mark-all-read/`, () => {
        markAllCalled = true
        return new HttpResponse(null, { status: 204 })
      })
    )
    renderWithQuery(<NotificationFeed />)
    const btn = await screen.findByRole('button', { name: /mark all read/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(markAllCalled).toBe(true)
    })
  })

  // ── individual mark as read ───────────────────────────────────────────────
  it('shows a "Mark as read" button only on unread notifications', async () => {
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('Contract Request')).toBeInTheDocument()
    })
    // Only the unread notification (notif-1) should have the mark-as-read button
    const markReadButtons = screen.getAllByRole('button', { name: /mark as read/i })
    expect(markReadButtons).toHaveLength(1)
  })

  it('calls the mark-as-read API when the button on an individual item is clicked', async () => {
    let markedId: string | undefined
    server.use(
      http.post(`${API}/api/notifications/:id/read/`, ({ params }) => {
        markedId = params.id as string
        return HttpResponse.json({
          id: params.id,
          project: 'proj-1',
          type: 'contract_request',
          is_read: true,
          triggered_by_contract_request: 'req-1',
          triggered_by_manager: null,
          created_at: '2026-03-30T12:00:00Z',
        })
      })
    )
    renderWithQuery(<NotificationFeed />)
    const btn = await screen.findByRole('button', { name: /mark as read/i })
    fireEvent.click(btn)
    await waitFor(() => {
      expect(markedId).toBe('notif-1')
    })
  })

  // ── notification icon rendering ───────────────────────────────────────────
  it('renders the correct icon colour class for contract_request type', async () => {
    renderWithQuery(<NotificationFeed />)
    await waitFor(() => {
      expect(screen.getByText('Contract Request')).toBeInTheDocument()
    })
    // The FileText icon for contract_request carries the blue text class
    const icons = document.querySelectorAll('.text-blue-500')
    expect(icons.length).toBeGreaterThan(0)
  })
})

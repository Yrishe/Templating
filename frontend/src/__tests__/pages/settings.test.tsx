import React from 'react'
import { screen, waitFor, fireEvent, renderWithQuery, mockUser } from '../test-utils'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/server'
import { SettingsContent } from '@/app/(app)/settings/settings-content'

// ─── mock useAuth ────────────────────────────────────────────────────────────
// SettingsContent depends on useAuth for the current user. We mock the hook
// directly so tests are not coupled to the AuthProvider's async bootstrap.

const mockRefreshUser = jest.fn().mockResolvedValue(undefined)

jest.mock('@/context/auth-context', () => ({
  useAuth: () => ({
    user: mockUser,
    isLoading: false,
    isAuthenticated: true,
    refreshUser: mockRefreshUser,
    login: jest.fn(),
    logout: jest.fn(),
    signup: jest.fn(),
  }),
}))

// ─── helpers ─────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

// ─── tests ───────────────────────────────────────────────────────────────────

describe('SettingsContent', () => {
  beforeEach(() => {
    mockRefreshUser.mockClear()
  })

  // ── rendering ─────────────────────────────────────────────────────────────
  it('renders the Settings heading', () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument()
  })

  it('pre-populates the first name and last name inputs with the current user', () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByLabelText(/first name/i)).toHaveValue('Alice')
    expect(screen.getByLabelText(/last name/i)).toHaveValue('Account')
  })

  it('displays the email as a read-only field', () => {
    renderWithQuery(<SettingsContent />)
    const emailInput = screen.getByDisplayValue('account@example.com')
    expect(emailInput).toHaveAttribute('readonly')
  })

  it('displays the user role badge', () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByText('account')).toBeInTheDocument()
  })

  it('renders the Save changes button', () => {
    renderWithQuery(<SettingsContent />)
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  // ── successful save ───────────────────────────────────────────────────────
  it('calls PATCH /api/auth/me/ with updated names on submit', async () => {
    let requestBody: Record<string, string> = {}
    server.use(
      http.patch(`${API}/api/auth/me/`, async ({ request }) => {
        requestBody = await request.json() as Record<string, string>
        return HttpResponse.json({ ...mockUser, ...requestBody })
      })
    )
    renderWithQuery(<SettingsContent />)

    fireEvent.change(screen.getByLabelText(/first name/i), {
      target: { value: 'Alexandra' },
    })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)

    await waitFor(() => {
      expect(requestBody.first_name).toBe('Alexandra')
      expect(requestBody.last_name).toBe('Account')
    })
  })

  it('shows "Changes saved." on successful save', async () => {
    server.use(
      http.patch(`${API}/api/auth/me/`, async ({ request }) => {
        const body = await request.json() as Record<string, string>
        return HttpResponse.json({ ...mockUser, ...body })
      })
    )
    renderWithQuery(<SettingsContent />)
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText(/changes saved/i)).toBeInTheDocument()
    })
  })

  it('calls refreshUser after a successful save', async () => {
    server.use(
      http.patch(`${API}/api/auth/me/`, async ({ request }) => {
        const body = await request.json() as Record<string, string>
        return HttpResponse.json({ ...mockUser, ...body })
      })
    )
    renderWithQuery(<SettingsContent />)
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)

    await waitFor(() => {
      expect(mockRefreshUser).toHaveBeenCalledTimes(1)
    })
  })

  // ── error state ───────────────────────────────────────────────────────────
  it('shows an error message when the save request fails', async () => {
    server.use(
      http.patch(`${API}/api/auth/me/`, () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    )
    renderWithQuery(<SettingsContent />)
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText(/failed to save/i)).toBeInTheDocument()
    })
  })

  // ── disabled while saving ─────────────────────────────────────────────────
  it('disables the Save button while the request is in-flight', async () => {
    // Use a never-resolving handler to keep the request pending
    server.use(
      http.patch(`${API}/api/auth/me/`, () => new Promise(() => {}))
    )
    renderWithQuery(<SettingsContent />)
    const form = screen.getByRole('button', { name: /save changes/i }).closest('form')!
    fireEvent.submit(form)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled()
    })
  })

  // ── validation guard ──────────────────────────────────────────────────────
  it('does not submit when first name is cleared', async () => {
    let requestMade = false
    server.use(
      http.patch(`${API}/api/auth/me/`, () => {
        requestMade = true
        return HttpResponse.json(mockUser)
      })
    )
    renderWithQuery(<SettingsContent />)
    fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: '' } })
    fireEvent.submit(screen.getByRole('button', { name: /save changes/i }).closest('form')!)

    // Give time for any async flow to complete
    await new Promise((r) => setTimeout(r, 50))
    expect(requestMade).toBe(false)
  })
})

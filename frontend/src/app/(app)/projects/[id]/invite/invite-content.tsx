'use client'

import React from 'react'
import { useParams } from 'next/navigation'
import { CheckCircle2, Search, UserPlus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/use-auth'
import { useProject, useProjectMembers } from '@/hooks/use-projects'
import { api } from '@/lib/api'
import type { User } from '@/types'
import { useQueryClient } from '@tanstack/react-query'
import { projectKeys } from '@/hooks/use-projects'

// Debounced user search against the same endpoint the create-project form
// uses (`GET /api/auth/users/search/?q=...`). Returns active users only and
// excludes the caller, so we don't need to filter the result list here.
function useUserSearch(query: string) {
  const [results, setResults] = React.useState<User[]>([])
  const [isSearching, setIsSearching] = React.useState(false)

  React.useEffect(() => {
    const q = query.trim()
    if (!q) {
      setResults([])
      return
    }
    let cancelled = false
    setIsSearching(true)
    const timer = setTimeout(() => {
      api
        .get<User[]>(`/api/auth/users/search/?q=${encodeURIComponent(q)}`)
        .then((res) => {
          if (!cancelled) setResults(res)
        })
        .catch(() => {
          if (!cancelled) setResults([])
        })
        .finally(() => {
          if (!cancelled) setIsSearching(false)
        })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  return { results, isSearching }
}

interface InviteResult {
  user: User
  status: 'ok' | 'error'
  message?: string
}

export function InvitePageContent() {
  const { id } = useParams<{ id: string }>()
  const { user: me } = useAuth()
  const { data: project } = useProject(id)
  const { data: membersData } = useProjectMembers(id)
  const queryClient = useQueryClient()

  const [query, setQuery] = React.useState('')
  const [selected, setSelected] = React.useState<User[]>([])
  const [submitting, setSubmitting] = React.useState(false)
  const [results, setResults] = React.useState<InviteResult[]>([])
  const { results: searchResults, isSearching } = useUserSearch(query)

  // Backend rule (backend/projects/views.py::ProjectMemberAddView): only the
  // manager or the project's account owner may invite. Show an explanatory
  // banner (and disable submit) if the current user isn't allowed — we're
  // optimistic about it client-side but the backend will still 403 anyway.
  const isManager = me?.role === 'manager'
  const isAccountOwner =
    !!project?.account_subscriber_id && project.account_subscriber_id === me?.id
  const canInvite = isManager || isAccountOwner

  // Hide users who are already members from the search results so we don't
  // repeatedly try to add them and stare at "already a member" errors.
  const existingMemberIds = React.useMemo(
    () => new Set((membersData?.results ?? []).map((m) => m.user)),
    [membersData]
  )
  const filteredResults = React.useMemo(
    () =>
      searchResults.filter(
        (u) =>
          !existingMemberIds.has(u.id) && !selected.find((s) => s.id === u.id)
      ),
    [searchResults, existingMemberIds, selected]
  )

  const toggleSelected = (user: User) => {
    setSelected((prev) =>
      prev.find((s) => s.id === user.id)
        ? prev.filter((s) => s.id !== user.id)
        : [...prev, user]
    )
    setResults([])
  }

  const removeSelected = (userId: string) => {
    setSelected((prev) => prev.filter((s) => s.id !== userId))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (selected.length === 0) return
    setSubmitting(true)
    // Fire all invites in parallel. Record per-user status so the UI can
    // show which succeeded and which failed (e.g. already a member).
    const settled = await Promise.allSettled(
      selected.map((u) =>
        api
          .post(`/api/projects/${id}/members/`, { user_id: u.id })
          .then(() => ({ user: u, status: 'ok' as const }))
      )
    )
    const next: InviteResult[] = settled.map((r, i) => {
      if (r.status === 'fulfilled') return r.value
      const msg = r.reason instanceof Error ? r.reason.message : 'Invite failed'
      return { user: selected[i], status: 'error' as const, message: msg }
    })
    setResults(next)
    // Clear only the ones that succeeded so the user can retry failures.
    setSelected((prev) =>
      prev.filter((u) => !next.find((r) => r.user.id === u.id && r.status === 'ok'))
    )
    setSubmitting(false)
    // Refresh the members list cache so `existingMemberIds` picks up the
    // new members for the next search.
    queryClient.invalidateQueries({ queryKey: projectKeys.members(id) })
  }

  const displayName = (u: User) =>
    u.first_name || u.last_name ? `${u.first_name} ${u.last_name}`.trim() : u.email

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <UserPlus className="h-4 w-4" />
            Invite members
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Search registered users and add them to this project. Invited
            members can chat, see the contract, and raise change requests.
          </p>
        </CardHeader>
        <CardContent>
          {!canInvite && (
            <div className="mb-4 rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
              Only the project owner or a manager can invite new members.
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="invite-search">Search by name or email</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="invite-search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. alice@example.com"
                  className="pl-8"
                  disabled={!canInvite}
                />
              </div>
            </div>

            {query.trim() && canInvite && (
              <div className="border rounded-md max-h-48 overflow-y-auto divide-y">
                {isSearching && (
                  <p className="p-2 text-xs text-muted-foreground">Searching...</p>
                )}
                {!isSearching && filteredResults.length === 0 && (
                  <p className="p-2 text-xs text-muted-foreground">
                    No matching registered users. (Already-added members are hidden.)
                  </p>
                )}
                {filteredResults.map((u) => (
                  <button
                    type="button"
                    key={u.id}
                    onClick={() => toggleSelected(u)}
                    className="w-full text-left p-2 text-sm flex items-center justify-between hover:bg-accent"
                  >
                    <div>
                      <div className="font-medium">{displayName(u)}</div>
                      <div className="text-xs text-muted-foreground">{u.email}</div>
                    </div>
                    <span className="text-xs text-muted-foreground capitalize">
                      {u.role.replace('_', ' ')}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {selected.length > 0 && (
              <div className="space-y-2">
                <Label>To invite</Label>
                <div className="flex flex-wrap gap-2">
                  {selected.map((u) => (
                    <span
                      key={u.id}
                      className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-xs"
                    >
                      {displayName(u)}
                      <button
                        type="button"
                        onClick={() => removeSelected(u.id)}
                        aria-label={`Remove ${u.email}`}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <Button
              type="submit"
              disabled={!canInvite || submitting || selected.length === 0}
            >
              <UserPlus className="h-4 w-4 mr-2" />
              {submitting
                ? 'Sending invites...'
                : `Invite ${selected.length || ''} ${
                    selected.length === 1 ? 'member' : 'members'
                  }`.trim()}
            </Button>
          </form>

          {results.length > 0 && (
            <div className="mt-6 space-y-2">
              {results.map((r) => (
                <div
                  key={r.user.id}
                  className={`flex items-start gap-2 rounded-md border p-3 text-sm ${
                    r.status === 'ok'
                      ? 'border-green-200 bg-green-50 text-green-800'
                      : 'border-red-200 bg-red-50 text-red-800'
                  }`}
                >
                  {r.status === 'ok' ? (
                    <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                  ) : (
                    <X className="h-4 w-4 mt-0.5 shrink-0" />
                  )}
                  <div>
                    <p className="font-medium">
                      {r.status === 'ok' ? 'Invited' : 'Could not invite'}{' '}
                      {displayName(r.user)}
                    </p>
                    {r.message && (
                      <p className="text-xs opacity-80">{r.message}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

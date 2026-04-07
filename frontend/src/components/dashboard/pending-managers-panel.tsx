'use client'

import React from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { UserCheck, X, Check } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatRelativeTime } from '@/lib/utils'

interface PendingManager {
  id: string
  email: string
  first_name: string
  last_name: string
  role: string
  date_joined: string
  last_login: string | null
}

const pendingManagerKeys = {
  all: ['pending-managers'] as const,
}

function usePendingManagers() {
  return useQuery({
    queryKey: pendingManagerKeys.all,
    queryFn: () => api.get<PendingManager[]>('/api/auth/pending-managers/'),
    refetchInterval: 60_000,
  })
}

function useApprovePendingManager() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.post(`/api/auth/pending-managers/${id}/approve/`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: pendingManagerKeys.all })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

function useRejectPendingManager() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/auth/pending-managers/${id}/reject/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: pendingManagerKeys.all })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function PendingManagersPanel() {
  const { data, isLoading } = usePendingManagers()
  const approve = useApprovePendingManager()
  const reject = useRejectPendingManager()

  const pending = data ?? []

  if (isLoading || pending.length === 0) return null

  return (
    <Card className="border-yellow-300 bg-yellow-50/40">
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <UserCheck className="h-5 w-5 text-yellow-700" />
          Pending Manager Requests
          <Badge variant="outline" className="ml-1">
            {pending.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {pending.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between gap-3 p-3 rounded-md border bg-background"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">
                {m.first_name} {m.last_name}
              </p>
              <p className="text-xs text-muted-foreground truncate">{m.email}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                Requested {formatRelativeTime(m.date_joined)}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={() => reject.mutate(m.id)}
                disabled={reject.isPending}
                aria-label={`Reject ${m.email}`}
              >
                <X className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                onClick={() => approve.mutate(m.id)}
                disabled={approve.isPending}
                aria-label={`Approve ${m.email}`}
              >
                <Check className="h-4 w-4 mr-1" />
                Approve
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

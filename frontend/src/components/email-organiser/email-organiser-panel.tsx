'use client'

import React, { useState } from 'react'
import { Mail, Inbox, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import type { IncomingEmail, PaginatedResponse } from '@/types'

interface EmailOrganiserPanelProps {
  projectId: string
}

function EmailItemRow({ email }: { email: IncomingEmail }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border rounded-md overflow-hidden">
      <button
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="mt-0.5 shrink-0 rounded-full bg-blue-100 p-1">
          <Mail className="h-3.5 w-3.5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-medium text-sm truncate">
              {email.subject || '(no subject)'}
            </span>
            {email.is_processed && (
              <Badge variant="outline" className="text-[10px] shrink-0">
                AI replied
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">
              From: {email.sender_name || email.sender_email}
            </span>
            <span className="shrink-0">{formatRelativeTime(email.received_at)}</span>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        )}
      </button>
      {expanded && (
        <div className="border-t bg-muted/20 p-3">
          <p className="text-sm whitespace-pre-wrap">{email.body_plain}</p>
        </div>
      )}
    </div>
  )
}

export function EmailOrganiserPanel({ projectId }: EmailOrganiserPanelProps) {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['incoming-emails', projectId],
    queryFn: () =>
      api.get<PaginatedResponse<IncomingEmail>>(
        `/api/projects/${projectId}/incoming-emails/`
      ),
    refetchInterval: 60_000,
  })

  const emails = data?.results ?? []

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Inbox className="h-5 w-5" />
            Incoming Emails
            {emails.length > 0 && (
              <Badge variant="secondary">{emails.length}</Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            aria-label="Refresh emails"
          >
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        )}
        {isError && (
          <div className="text-center py-8">
            <p className="text-sm text-destructive">Failed to load emails</p>
            <Button variant="outline" size="sm" className="mt-2" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        )}
        {!isLoading && !isError && emails.length === 0 && (
          <div className="text-center py-10">
            <Mail className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
            <p className="text-sm text-muted-foreground">No emails received yet</p>
          </div>
        )}
        {!isLoading && !isError && emails.length > 0 && (
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {emails.map((email) => (
              <EmailItemRow key={email.id} email={email} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

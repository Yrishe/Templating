'use client'

import React, { useState } from 'react'
import {
  Mail,
  Inbox,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Filter,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatRelativeTime } from '@/lib/utils'
import { useIncomingEmails } from '@/hooks/use-email-organiser'
import { AiFeedback } from '@/components/feedback/ai-feedback'
import type { IncomingEmail, EmailCategory, EmailRelevance } from '@/types'

// ─── Category & relevance config ─────────────────────────────────────

const CATEGORY_CONFIG: Record<EmailCategory, { label: string; color: string }> = {
  delay: { label: 'Delay', color: 'bg-amber-100 text-amber-800 border-amber-200' },
  damage: { label: 'Damage', color: 'bg-red-100 text-red-800 border-red-200' },
  scope_change: { label: 'Scope Change', color: 'bg-purple-100 text-purple-800 border-purple-200' },
  costs: { label: 'Costs', color: 'bg-orange-100 text-orange-800 border-orange-200' },
  delivery: { label: 'Delivery', color: 'bg-blue-100 text-blue-800 border-blue-200' },
  compliance: { label: 'Compliance', color: 'bg-teal-100 text-teal-800 border-teal-200' },
  quality: { label: 'Quality', color: 'bg-pink-100 text-pink-800 border-pink-200' },
  dispute: { label: 'Dispute', color: 'bg-rose-100 text-rose-800 border-rose-200' },
  general: { label: 'General', color: 'bg-gray-100 text-gray-800 border-gray-200' },
  irrelevant: { label: 'Irrelevant', color: 'bg-gray-50 text-gray-400 border-gray-100' },
}

const RELEVANCE_CONFIG: Record<EmailRelevance, { label: string; variant: 'destructive' | 'warning' | 'outline' | 'secondary' }> = {
  high: { label: 'High', variant: 'destructive' },
  medium: { label: 'Medium', variant: 'warning' },
  low: { label: 'Low', variant: 'outline' },
  none: { label: 'None', variant: 'secondary' },
}

export function CategoryBadge({ category }: { category: EmailCategory }) {
  const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG.general
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${config.color}`}>
      {config.label}
    </span>
  )
}

export function RelevanceBadge({ relevance }: { relevance: EmailRelevance }) {
  const config = RELEVANCE_CONFIG[relevance] || RELEVANCE_CONFIG.medium
  return <Badge variant={config.variant} className="text-[10px]">{config.label}</Badge>
}

// ─── Email row ───────────────────────────────────────────────────────

function EmailItemRow({
  email,
  isSelected,
  onSelect,
}: {
  email: IncomingEmail
  isSelected: boolean
  onSelect: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`border rounded-md overflow-hidden transition-colors ${
        isSelected ? 'border-primary ring-1 ring-primary/30' : ''
      } ${email.is_resolved ? 'opacity-60' : ''}`}
    >
      <button
        className="w-full flex items-start gap-3 p-3 text-left hover:bg-muted/50 transition-colors"
        onClick={() => {
          onSelect()
          setExpanded(!expanded)
        }}
      >
        <div className="mt-0.5 shrink-0">
          {email.is_resolved ? (
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          ) : email.relevance === 'high' ? (
            <AlertTriangle className="h-4 w-4 text-red-500" />
          ) : (
            <Mail className="h-4 w-4 text-blue-500" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
            <span className="font-medium text-sm truncate">
              {email.subject || '(no subject)'}
            </span>
            <CategoryBadge category={email.category} />
            <RelevanceBadge relevance={email.relevance} />
            {email.is_resolved && (
              <Badge variant="success" className="text-[10px]">Resolved</Badge>
            )}
            {!email.is_processed && (
              <Badge variant="outline" className="text-[10px] gap-1">
                <Clock className="h-2.5 w-2.5" /> Processing
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate">
              {email.sender_name || email.sender_email}
            </span>
            <span className="shrink-0">{formatRelativeTime(email.received_at)}</span>
          </div>
          {email.keywords && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {email.keywords.split(',').slice(0, 5).map((kw, i) => (
                <span
                  key={i}
                  className="inline-block rounded bg-muted px-1.5 py-0 text-[10px] text-muted-foreground"
                >
                  {kw.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
        )}
      </button>
      {expanded && (
        <div className="border-t bg-muted/20 p-3 space-y-3">
          <p className="text-sm whitespace-pre-wrap">{email.body_plain}</p>
          <div className="flex items-start justify-between gap-3">
            <span className="text-[11px] text-muted-foreground">
              How did the AI classify this one?
            </span>
            <AiFeedback targetType="classification" targetId={email.id} />
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main panel ──────────────────────────────────────────────────────

interface EmailOrganiserPanelProps {
  projectId: string
  selectedEmailId?: string | null
  onSelectEmail?: (email: IncomingEmail) => void
  categoryFilter?: string
  relevanceFilter?: string
  showResolved?: boolean
}

export function EmailOrganiserPanel({
  projectId,
  selectedEmailId,
  onSelectEmail,
  categoryFilter,
  relevanceFilter,
  showResolved = false,
}: EmailOrganiserPanelProps) {
  const { data, isLoading, isError, refetch, isFetching } = useIncomingEmails({
    projectId,
    category: categoryFilter,
    relevance: relevanceFilter,
    is_resolved: showResolved ? undefined : 'false',
    is_relevant: 'true',
  })

  const emails = data?.results ?? []

  // Group by category for summary counts
  const categoryCounts = emails.reduce((acc, e) => {
    acc[e.category] = (acc[e.category] || 0) + 1
    return acc
  }, {} as Record<string, number>)

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
        {/* Category summary */}
        {Object.keys(categoryCounts).length > 1 && (
          <div className="flex gap-2 flex-wrap mt-2">
            {Object.entries(categoryCounts).map(([cat, count]) => (
              <span key={cat} className="text-xs text-muted-foreground">
                {CATEGORY_CONFIG[cat as EmailCategory]?.label ?? cat}: {count}
              </span>
            ))}
          </div>
        )}
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
            <p className="text-sm text-muted-foreground">No emails to display</p>
          </div>
        )}
        {!isLoading && !isError && emails.length > 0 && (
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {emails.map((email) => (
              <EmailItemRow
                key={email.id}
                email={email}
                isSelected={selectedEmailId === email.id}
                onSelect={() => onSelectEmail?.(email)}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

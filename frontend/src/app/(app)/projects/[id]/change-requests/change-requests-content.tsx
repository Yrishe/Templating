'use client'

import React, { useState } from 'react'
import { useParams } from 'next/navigation'
import {
  CheckCircle,
  Clock,
  FileText,
  ThumbsDown,
  ThumbsUp,
  X,
  FilePen,
  AlertTriangle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  useContractRequests,
  useApproveContractRequest,
  useRejectContractRequest,
  useProject,
} from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDateTime } from '@/lib/utils'
import type { ContractRequest, ContractRequestStatus } from '@/types'

// ─── Status chip ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  ContractRequestStatus,
  { variant: 'warning' | 'success' | 'destructive'; label: string; Icon: typeof Clock }
> = {
  pending: { variant: 'warning', label: 'Pending', Icon: Clock },
  approved: { variant: 'success', label: 'Approved', Icon: CheckCircle },
  rejected: { variant: 'destructive', label: 'Rejected', Icon: X },
}

function StatusBadge({ status }: { status: ContractRequestStatus }) {
  const { variant, label, Icon } = STATUS_CONFIG[status]
  return (
    <Badge variant={variant} className="flex items-center gap-1">
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  )
}

// ─── Attachment link ─────────────────────────────────────────────────────────

function AttachmentLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
    >
      <FileText className="h-3.5 w-3.5" />
      View attached file
    </a>
  )
}

// ─── Manager review actions (only rendered for pending rows) ─────────────────

interface ReviewActionsProps {
  projectId: string
  request: ContractRequest
}

function ReviewActions({ projectId, request }: ReviewActionsProps) {
  const approve = useApproveContractRequest(projectId)
  const reject = useRejectContractRequest(projectId)
  const [comment, setComment] = useState('')
  const busy = approve.isPending || reject.isPending

  return (
    <div className="space-y-2 mt-3">
      <Label htmlFor={`review-comment-${request.id}`} className="text-xs">
        Justification (optional)
      </Label>
      <textarea
        id={`review-comment-${request.id}`}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Explain why you're approving or rejecting this request..."
        className="flex min-h-[60px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
      />
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() =>
            approve.mutate(
              { id: request.id, review_comment: comment },
              { onSuccess: () => setComment('') }
            )
          }
          disabled={busy}
        >
          <ThumbsUp className="h-3.5 w-3.5 mr-1.5" />
          Approve
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() =>
            reject.mutate(
              { id: request.id, review_comment: comment },
              { onSuccess: () => setComment('') }
            )
          }
          disabled={busy}
        >
          <ThumbsDown className="h-3.5 w-3.5 mr-1.5" />
          Reject
        </Button>
      </div>
    </div>
  )
}

// ─── Single request row ──────────────────────────────────────────────────────

interface RequestRowProps {
  projectId: string
  request: ContractRequest
  canReview: boolean
}

function RequestRow({ projectId, request, canReview }: RequestRowProps) {
  return (
    <div className="border rounded-md p-4 space-y-2">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">Change request</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Submitted {formatDateTime(request.created_at)}
          </p>
        </div>
        <StatusBadge status={request.status} />
      </div>
      <p className="text-sm whitespace-pre-wrap">{request.description}</p>
      {request.attachment_url && <AttachmentLink url={request.attachment_url} />}
      {request.reviewed_at && (
        <p className="text-xs text-muted-foreground">
          Reviewed {formatDateTime(request.reviewed_at)}
        </p>
      )}
      {request.review_comment && (
        <div className="rounded-md border bg-muted/40 p-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">
            Manager's note
          </p>
          <p className="text-sm whitespace-pre-wrap">{request.review_comment}</p>
        </div>
      )}
      {canReview && request.status === 'pending' && (
        <ReviewActions projectId={projectId} request={request} />
      )}
    </div>
  )
}

// ─── Main page content ──────────────────────────────────────────────────────

export function ChangeRequestsContent() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const { data: project } = useProject(id)
  const { data, isLoading, isError } = useContractRequests(id)

  const requests = data?.results ?? []
  const pending = requests.filter((r) => r.status === 'pending')
  const history = requests.filter((r) => r.status !== 'pending')

  const isManager = user?.role === 'manager'
  // A manager on a project they created and kept assigned to themselves
  // shouldn't be approving their own requests — mirrors the overview rule.
  const isManagerSelfOwned =
    isManager &&
    !!project?.account_subscriber_id &&
    project.account_subscriber_id === user?.id
  const canReview = isManager && !isManagerSelfOwned

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="h-32 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-10 w-10 text-destructive mx-auto mb-3" />
        <p className="text-muted-foreground">Failed to load change requests</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FilePen className="h-4 w-4" />
            Pending
            {pending.length > 0 && (
              <Badge variant="warning">{pending.length}</Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">
              No pending change requests.
            </p>
          ) : (
            <div className="space-y-3">
              {pending.map((req) => (
                <RequestRow
                  key={req.id}
                  projectId={id}
                  request={req}
                  canReview={canReview}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">History</CardTitle>
          <p className="text-sm text-muted-foreground">
            All approved and rejected change requests for this project.
          </p>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">
              No past change requests yet.
            </p>
          ) : (
            <div className="space-y-3">
              {history.map((req) => (
                <RequestRow
                  key={req.id}
                  projectId={id}
                  request={req}
                  canReview={false}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

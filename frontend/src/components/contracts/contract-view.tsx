'use client'

import React, { useRef, useState } from 'react'
import {
  FileText, Upload, CheckCircle, Clock, AlertTriangle,
  Download, ThumbsUp, ThumbsDown, Send, X,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  useProjectContract,
  useCreateContract,
  useUpdateContract,
  useActivateContract,
  useContractRequests,
  useCreateContractRequest,
  useApproveContractRequest,
  useRejectContractRequest,
} from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDateTime } from '@/lib/utils'
import type { Contract, ContractRequest } from '@/types'

// ─── Status badge ────────────────────────────────────────────────────────────

function ContractStatusBadge({ status }: { status: Contract['status'] }) {
  const config = {
    draft: { variant: 'warning' as const, icon: Clock, label: 'Draft' },
    active: { variant: 'success' as const, icon: CheckCircle, label: 'Active' },
    expired: { variant: 'secondary' as const, icon: AlertTriangle, label: 'Expired' },
  }[status]
  const Icon = config.icon
  return (
    <Badge variant={config.variant} className="flex items-center gap-1">
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  )
}

// ─── Account: Upload contract PDF ────────────────────────────────────────────

interface UploadContractProps {
  projectId: string
  existingContract: Contract | null
}

function UploadContractForm({ projectId, existingContract }: UploadContractProps) {
  const [title, setTitle] = useState(existingContract?.title ?? '')
  const [file, setFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const createContract = useCreateContract()
  const updateContract = useUpdateContract(existingContract?.id ?? '', projectId)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title) return
    const form = new FormData()
    form.append('project', projectId)
    form.append('title', title)
    if (file) form.append('file', file)

    if (existingContract) {
      const updateForm = new FormData()
      updateForm.append('title', title)
      if (file) updateForm.append('file', file)
      await updateContract.mutateAsync(updateForm)
    } else {
      await createContract.mutateAsync(form)
    }
    setFile(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const isPending = createContract.isPending || updateContract.isPending

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="contract-title">Contract title</Label>
        <Input
          id="contract-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Vendor Agreement 2026"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="contract-file">
          PDF file {existingContract?.file_url ? '(upload to replace)' : '*'}
        </Label>
        <input
          id="contract-file"
          ref={fileRef}
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
          required={!existingContract}
        />
        {existingContract?.file_url && (
          <p className="text-xs text-muted-foreground">
            Current file uploaded. Select a new file only if you want to replace it.
          </p>
        )}
      </div>
      {(createContract.isError || updateContract.isError) && (
        <p className="text-sm text-destructive">Failed to save contract. Please try again.</p>
      )}
      <Button type="submit" disabled={isPending}>
        <Upload className="h-4 w-4 mr-2" />
        {isPending ? 'Saving...' : existingContract ? 'Update contract' : 'Upload contract'}
      </Button>
    </form>
  )
}

// ─── Account: Submit contract request ────────────────────────────────────────

interface SubmitRequestProps {
  projectId: string
  accountId: string
  existingRequest: ContractRequest | null
}

function SubmitRequestForm({ projectId, accountId, existingRequest }: SubmitRequestProps) {
  const [description, setDescription] = useState('')
  const createRequest = useCreateContractRequest()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await createRequest.mutateAsync({ project: projectId, account: accountId, description })
    setDescription('')
  }

  if (existingRequest) {
    const statusConfig = {
      pending: { variant: 'warning' as const, label: 'Pending review', icon: Clock },
      approved: { variant: 'success' as const, label: 'Approved', icon: CheckCircle },
      rejected: { variant: 'destructive' as const, label: 'Rejected', icon: X },
    }[existingRequest.status]
    const Icon = statusConfig.icon
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Badge variant={statusConfig.variant} className="flex items-center gap-1">
            <Icon className="h-3 w-3" />
            {statusConfig.label}
          </Badge>
          {existingRequest.reviewed_at && (
            <span className="text-xs text-muted-foreground">
              Reviewed {formatDateTime(existingRequest.reviewed_at)}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{existingRequest.description}</p>
        {existingRequest.status === 'rejected' && (
          <p className="text-xs text-destructive">
            Your request was rejected. Update your contract and submit a new request.
          </p>
        )}
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor="request-description">Description / terms summary</Label>
        <textarea
          id="request-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Briefly describe the contract terms you're submitting for approval..."
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
          required
        />
      </div>
      {createRequest.isError && (
        <p className="text-sm text-destructive">Failed to submit request. Please try again.</p>
      )}
      <Button type="submit" disabled={createRequest.isPending || !description.trim()}>
        <Send className="h-4 w-4 mr-2" />
        {createRequest.isPending ? 'Submitting...' : 'Submit for approval'}
      </Button>
    </form>
  )
}

// ─── Manager: Review contract requests ───────────────────────────────────────

interface ReviewPanelProps {
  projectId: string
  requests: ContractRequest[]
}

function ContractRequestReviewPanel({ projectId, requests }: ReviewPanelProps) {
  const approve = useApproveContractRequest(projectId)
  const reject = useRejectContractRequest(projectId)
  const pending = requests.filter((r) => r.status === 'pending')

  if (pending.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">No pending contract requests.</p>
    )
  }

  return (
    <div className="space-y-3">
      {pending.map((req) => (
        <div key={req.id} className="border rounded-md p-4 space-y-3">
          <div>
            <p className="text-sm font-medium">Contract request</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Submitted {formatDateTime(req.created_at)}
            </p>
          </div>
          <p className="text-sm">{req.description}</p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => approve.mutate(req.id)}
              disabled={approve.isPending || reject.isPending}
            >
              <ThumbsUp className="h-3.5 w-3.5 mr-1.5" />
              Approve
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => reject.mutate(req.id)}
              disabled={approve.isPending || reject.isPending}
            >
              <ThumbsDown className="h-3.5 w-3.5 mr-1.5" />
              Reject
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Main contract view ───────────────────────────────────────────────────────

interface ContractViewProps {
  projectId: string
}

export function ContractView({ projectId }: ContractViewProps) {
  const { user } = useAuth()
  const { data, isLoading, isError } = useProjectContract(projectId)
  const { data: requestsData } = useContractRequests(projectId)
  const activate = useActivateContract(projectId)

  const contract = data?.results?.[0] ?? null
  const requests = requestsData?.results ?? []
  const latestRequest = requests[0] ?? null

  const isManager = user?.role === 'manager'
  const isAccount = user?.role === 'account'

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
        <p className="text-muted-foreground">Failed to load contract</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Contract file card */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <FileText className="h-5 w-5 text-primary shrink-0" />
              <CardTitle className="text-lg">
                {contract ? contract.title : 'No contract yet'}
              </CardTitle>
            </div>
            {contract && (
              <div className="flex items-center gap-2 shrink-0">
                <ContractStatusBadge status={contract.status} />
                {isManager && contract.status === 'draft' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => activate.mutate(contract.id)}
                    disabled={activate.isPending}
                    className="text-xs"
                  >
                    <CheckCircle className="h-3.5 w-3.5 mr-1" />
                    Activate
                  </Button>
                )}
              </div>
            )}
          </div>
          {contract && (
            <div className="flex gap-4 text-xs text-muted-foreground mt-1">
              <span>Created: {formatDateTime(contract.created_at)}</span>
              {contract.activated_at && (
                <span>Activated: {formatDateTime(contract.activated_at)}</span>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent>
          {/* PDF viewer / download */}
          {contract?.file_url && (
            <div className="mb-4 p-3 rounded-md bg-muted/40 border flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="h-4 w-4 text-primary shrink-0" />
                <span className="text-sm truncate">Contract PDF</span>
              </div>
              <a href={contract.file_url} target="_blank" rel="noopener noreferrer">
                <Button size="sm" variant="outline">
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  Download / View
                </Button>
              </a>
            </div>
          )}

          {/* Upload form — accounts always; managers when they own / have not
              yet uploaded a contract for this project. */}
          {(isAccount || isManager) && (
            <UploadContractForm projectId={projectId} existingContract={contract} />
          )}
        </CardContent>
      </Card>

      {/* Contract request panel */}
      {isAccount && contract && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Approval request</CardTitle>
            <p className="text-sm text-muted-foreground">
              Submit your contract for Manager review and approval.
            </p>
          </CardHeader>
          <CardContent>
            <SubmitRequestForm
              projectId={projectId}
              accountId={contract.project}
              existingRequest={latestRequest}
            />
          </CardContent>
        </Card>
      )}

      {/* Manager: contract request review */}
      {isManager && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              Contract Requests
              {requests.filter((r) => r.status === 'pending').length > 0 && (
                <Badge variant="warning">
                  {requests.filter((r) => r.status === 'pending').length} pending
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ContractRequestReviewPanel projectId={projectId} requests={requests} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

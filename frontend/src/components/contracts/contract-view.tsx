'use client'

import React, { useRef, useState } from 'react'
import {
  FileText, Upload, CheckCircle, CheckCircle2, Clock, AlertTriangle,
  Download, Send,
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
  useCreateContractRequest,
} from '@/hooks/use-projects'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { projectKeys } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDateTime } from '@/lib/utils'
import type { Contract } from '@/types'

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
  // Tracks whether the *most recent* user action was a successful save, so
  // the banner clears as soon as they start editing the form again. Not
  // tied to mutation.isSuccess because that stays true until reset and
  // would reappear on unrelated re-renders.
  const [justSaved, setJustSaved] = useState<null | 'created' | 'updated'>(null)
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
      setJustSaved('updated')
    } else {
      await createContract.mutateAsync(form)
      setJustSaved('created')
    }
    setFile(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  const isPending = createContract.isPending || updateContract.isPending
  // Any further edit to the form clears the banner — it's an acknowledgement
  // gesture, no setTimeout needed.
  const handleTitleChange = (value: string) => {
    setTitle(value)
    if (justSaved) setJustSaved(null)
  }
  const handleFileChange = (next: File | null) => {
    setFile(next)
    if (justSaved) setJustSaved(null)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="contract-title">Contract title</Label>
        <Input
          id="contract-title"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
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
          onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
          required={!existingContract}
        />
        {existingContract?.file_url && (
          <p className="text-xs text-muted-foreground">
            Current file uploaded. Select a new file only if you want to replace it.
          </p>
        )}
      </div>
      {justSaved && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800"
        >
          <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">
              {justSaved === 'created' ? 'Contract uploaded' : 'Contract updated'}
            </p>
            <p className="text-xs text-green-700">
              {justSaved === 'created'
                ? 'Your contract has been saved and is ready for review.'
                : 'Your changes to the contract have been saved.'}
            </p>
          </div>
        </div>
      )}
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

// ─── Account: Submit contract change request ─────────────────────────────────

interface SubmitRequestProps {
  projectId: string
}

function SubmitRequestForm({ projectId }: SubmitRequestProps) {
  const [description, setDescription] = useState('')
  const [attachment, setAttachment] = useState<File | null>(null)
  const attachmentRef = useRef<HTMLInputElement>(null)
  const createRequest = useCreateContractRequest()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // `account` is now assigned server-side from the project; the client only
    // needs to supply the project, description, and (optionally) a file.
    if (attachment) {
      const form = new FormData()
      form.append('project', projectId)
      form.append('description', description)
      form.append('attachment', attachment)
      await createRequest.mutateAsync(form)
    } else {
      await createRequest.mutateAsync({ project: projectId, description })
    }
    setDescription('')
    setAttachment(null)
    if (attachmentRef.current) attachmentRef.current.value = ''
  }

  // Show the success banner after a submit until the user starts typing
  // a new request — that's a natural "acknowledge" gesture that doesn't
  // need a setTimeout, toast library, or manual dismiss button.
  const showSuccess = createRequest.isSuccess && description === '' && !attachment
  const handleDescriptionChange = (value: string) => {
    setDescription(value)
    if (createRequest.isSuccess && value !== '') {
      createRequest.reset()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor="request-description">Change request details</Label>
        <textarea
          id="request-description"
          value={description}
          onChange={(e) => handleDescriptionChange(e.target.value)}
          placeholder="Describe the change you're requesting on the contract..."
          className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="request-attachment">Supporting file (optional)</Label>
        <input
          id="request-attachment"
          ref={attachmentRef}
          type="file"
          accept=".pdf"
          onChange={(e) => {
            const file = e.target.files?.[0] ?? null
            if (file && file.size > 10 * 1024 * 1024) {
              alert('File is too large. Maximum size is 10 MB.')
              e.target.value = ''
              setAttachment(null)
              return
            }
            setAttachment(file)
          }}
          className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-primary file:text-primary-foreground hover:file:bg-primary/90 cursor-pointer"
        />
        <p className="text-xs text-muted-foreground">
          PDF only, max 10 MB. Attach a redlined contract or supporting document for the manager to review.
        </p>
      </div>
      {showSuccess && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-800"
        >
          <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Change request submitted</p>
            <p className="text-xs text-green-700">
              The manager will review it. You can track its status on the{' '}
              Change Requests tab.
            </p>
          </div>
        </div>
      )}
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

// ─── Contract text extraction info + manual paste ────────────────────────────

function ContractTextSection({ contract, projectId }: { contract: Contract; projectId: string }) {
  const [showPaste, setShowPaste] = useState(false)
  const [manualText, setManualText] = useState(contract.content)
  const queryClient = useQueryClient()

  const saveText = useMutation({
    mutationFn: (content: string) =>
      api.patch<Contract>(`/api/contracts/${contract.id}/`, { content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contract(projectId) })
      setShowPaste(false)
    },
  })

  const sourceLabels: Record<string, { text: string; className: string }> = {
    pypdf: { text: 'Text extracted from digital PDF', className: 'text-green-700 bg-green-50 border-green-200' },
    textract: { text: 'Text extracted via OCR (AWS Textract) — quality may vary', className: 'text-amber-700 bg-amber-50 border-amber-200' },
    manual: { text: 'Text pasted manually', className: 'text-blue-700 bg-blue-50 border-blue-200' },
    none: { text: 'No text extracted — the AI pipeline needs contract text to analyse emails', className: 'text-red-700 bg-red-50 border-red-200' },
  }

  const source = sourceLabels[contract.text_source] ?? sourceLabels.none

  return (
    <div className="mt-4 space-y-3">
      <div className={`rounded-md border p-3 text-xs ${source.className}`}>
        <div className="flex items-center justify-between">
          <span>{source.text}</span>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 px-2 text-[11px]"
            onClick={() => {
              setManualText(contract.content)
              setShowPaste(!showPaste)
            }}
          >
            {showPaste ? 'Cancel' : 'Paste text manually'}
          </Button>
        </div>
      </div>

      {showPaste && (
        <div className="space-y-2">
          <Label htmlFor="manual-content">Contract text</Label>
          <textarea
            id="manual-content"
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
            placeholder="Paste the full contract text here..."
            className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => saveText.mutate(manualText)}
              disabled={saveText.isPending || !manualText.trim()}
            >
              {saveText.isPending ? 'Saving...' : 'Save contract text'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowPaste(false)}
            >
              Cancel
            </Button>
          </div>
          {saveText.isError && (
            <p className="text-sm text-destructive">Failed to save text.</p>
          )}
        </div>
      )}
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
  const activate = useActivateContract(projectId)

  const contract = data?.results?.[0] ?? null

  const isManager = user?.role === 'manager'
  const isAccount = user?.role === 'account'
  // Contract change requests can be raised by Account users (creator) AND
  // invited users, per the project's collaboration rules — both are project
  // members with a non-manager role.
  const canRaiseRequest = !!user && user.role !== 'manager'

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

          {/* Text extraction source banner + manual paste fallback */}
          {contract && (
            <ContractTextSection contract={contract} projectId={projectId} />
          )}
        </CardContent>
      </Card>

      {/* Change request input — any non-manager project member can raise
          a change request at any time as long as a contract has been
          uploaded. Unlike the previous version this stays available even
          when there are already pending/approved/rejected requests in
          flight; the full history lives on the Change Requests tab. */}
      {canRaiseRequest && contract && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Request a contract change</CardTitle>
            <p className="text-sm text-muted-foreground">
              Describe the change you'd like and, optionally, attach a
              supporting file. The manager will review it on the Change
              Requests tab.
            </p>
          </CardHeader>
          <CardContent>
            <SubmitRequestForm projectId={projectId} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}

'use client'

import React, { useState } from 'react'
import { FileText, Edit3, CheckCircle, Clock, AlertTriangle, Save, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useProjectContract, useUpdateContract } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDateTime } from '@/lib/utils'
import type { Contract } from '@/types'

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

interface ContractEditorProps {
  contract: Contract
  onClose: () => void
}

function ContractEditor({ contract, onClose }: ContractEditorProps) {
  const [title, setTitle] = useState(contract.title)
  const [content, setContent] = useState(contract.content)
  const updateContract = useUpdateContract(contract.id, contract.project)

  const handleSave = async () => {
    await updateContract.mutateAsync({ title, content })
    onClose()
  }

  return (
    <div className="space-y-4">
      <input
        className="w-full text-xl font-semibold border-b border-input bg-transparent pb-2 focus:outline-none focus:border-primary"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Contract title"
      />
      <textarea
        className="w-full min-h-[400px] rounded-md border border-input bg-background p-4 text-sm font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-y"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Contract content..."
      />
      <div className="flex gap-2">
        <Button onClick={handleSave} disabled={updateContract.isPending}>
          <Save className="h-4 w-4 mr-2" />
          {updateContract.isPending ? 'Saving...' : 'Save Changes'}
        </Button>
        <Button variant="outline" onClick={onClose}>
          <X className="h-4 w-4 mr-2" />
          Cancel
        </Button>
      </div>
    </div>
  )
}

interface ContractViewProps {
  projectId: string
}

export function ContractView({ projectId }: ContractViewProps) {
  const { user } = useAuth()
  const { data, isLoading, isError } = useProjectContract(projectId)
  const [editingId, setEditingId] = useState<string | null>(null)
  const updateContract = useUpdateContract(editingId ?? '', projectId)

  const contracts = data?.results ?? []
  const isManager = user?.role === 'manager'

  const handleActivate = async (contract: Contract) => {
    await updateContract.mutateAsync({ status: 'active', activated_at: new Date().toISOString() })
  }

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
        <p className="text-muted-foreground">Failed to load contracts</p>
      </div>
    )
  }

  if (contracts.length === 0) {
    return (
      <div className="text-center py-16">
        <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
        <h3 className="font-semibold mb-1">No contracts yet</h3>
        <p className="text-sm text-muted-foreground">
          {isManager
            ? 'Create a contract to get started.'
            : 'No contracts have been created for this project.'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {contracts.map((contract) => (
        <Card key={contract.id}>
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-5 w-5 text-primary shrink-0" />
                <CardTitle className="text-lg truncate">{contract.title}</CardTitle>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <ContractStatusBadge status={contract.status} />
                {isManager && (
                  <div className="flex gap-1">
                    {contract.status === 'draft' && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleActivate(contract)}
                        className="text-xs"
                      >
                        <CheckCircle className="h-3.5 w-3.5 mr-1" />
                        Activate
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        setEditingId(editingId === contract.id ? null : contract.id)
                      }
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-4 text-xs text-muted-foreground mt-2">
              <span>Created: {formatDateTime(contract.created_at)}</span>
              {contract.activated_at && (
                <span>Activated: {formatDateTime(contract.activated_at)}</span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {editingId === contract.id ? (
              <ContractEditor contract={contract} onClose={() => setEditingId(null)} />
            ) : (
              <div className="prose prose-sm max-w-none">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed bg-muted/30 rounded-md p-4 overflow-auto max-h-96">
                  {contract.content}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

'use client'

import React from 'react'
import { useParams } from 'next/navigation'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ContractView } from '@/components/contracts/contract-view'
import { useAuth } from '@/hooks/use-auth'
import { useCreateContract } from '@/hooks/use-projects'

export function ContractPageContent() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const createContract = useCreateContract()
  const isManager = user?.role === 'manager'

  return (
    <div className="space-y-4">
      {isManager && (
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={() =>
              createContract.mutate({
                project: id,
                title: 'New Contract',
                content: '',
                status: 'draft',
              })
            }
            disabled={createContract.isPending}
          >
            <Plus className="h-4 w-4 mr-2" />
            New Contract
          </Button>
        </div>
      )}
      <ContractView projectId={id} />
    </div>
  )
}

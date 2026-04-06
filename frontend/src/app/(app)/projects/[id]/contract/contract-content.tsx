'use client'

import React from 'react'
import { useParams } from 'next/navigation'
import { ContractView } from '@/components/contracts/contract-view'

export function ContractPageContent() {
  const { id } = useParams<{ id: string }>()
  return <ContractView projectId={id} />
}

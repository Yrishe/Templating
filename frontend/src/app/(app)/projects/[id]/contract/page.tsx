import type { Metadata } from 'next'
import { ContractPageContent } from './contract-content'

export const metadata: Metadata = { title: 'Contract' }

export default function ContractPage() {
  return <ContractPageContent />
}

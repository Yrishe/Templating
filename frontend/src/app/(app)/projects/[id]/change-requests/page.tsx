import type { Metadata } from 'next'
import { ChangeRequestsContent } from './change-requests-content'

export const metadata: Metadata = { title: 'Change Requests' }

export default function ChangeRequestsPage() {
  return <ChangeRequestsContent />
}

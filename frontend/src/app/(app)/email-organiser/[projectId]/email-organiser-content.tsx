'use client'

import { useParams } from 'next/navigation'
import { EmailOrganiserPanel } from '@/components/email-organiser/email-organiser-panel'
import { FinalResponseEditor } from '@/components/email-organiser/final-response-editor'

export function EmailOrganiserContent() {
  const { projectId } = useParams<{ projectId: string }>()

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Email Organiser</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EmailOrganiserPanel projectId={projectId} />
        <FinalResponseEditor projectId={projectId} />
      </div>
    </div>
  )
}

'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { EmailOrganiserPanel } from '@/components/email-organiser/email-organiser-panel'
import { ReplyPanel } from '@/components/email-organiser/reply-panel'
import type { IncomingEmail } from '@/types'

export function EmailOrganiserContent() {
  const { projectId } = useParams<{ projectId: string }>()
  const [selected, setSelected] = useState<IncomingEmail | null>(null)

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Email Organiser</h2>
      <p className="text-sm text-muted-foreground">
        Select an inbound email on the left and the AI will dynamically draft a
        Reply on the right, grounded in the project&apos;s contract.
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EmailOrganiserPanel
          projectId={projectId}
          selectedEmailId={selected?.id ?? null}
          onSelectEmail={setSelected}
        />
        <ReplyPanel projectId={projectId} email={selected} />
      </div>
    </div>
  )
}

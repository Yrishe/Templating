'use client'

import { useParams } from 'next/navigation'
import { TimelineView } from '@/components/timeline/timeline-view'

export function TimelinePageContent() {
  const { id } = useParams<{ id: string }>()
  return <TimelineView projectId={id} />
}

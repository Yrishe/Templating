import type { Metadata } from 'next'
import { TimelinePageContent } from './timeline-content'

export const metadata: Metadata = { title: 'Timeline' }

export default function TimelinePage() {
  return <TimelinePageContent />
}

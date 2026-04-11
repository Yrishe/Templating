import type { Metadata } from 'next'
import { InvitePageContent } from './invite-content'

export const metadata: Metadata = { title: 'Invite members' }

export default function InvitePage() {
  return <InvitePageContent />
}

import type { Metadata } from 'next'
import { EmailOrganiserContent } from './email-organiser-content'

export const metadata: Metadata = { title: 'Email Organiser' }

export default function EmailOrganiserPage() {
  return <EmailOrganiserContent />
}

import type { Metadata } from 'next'
import { ProfileContent } from './profile-content'

export const metadata: Metadata = { title: 'Profile' }

export default function ProfilePage({ params }: { params: { id: string } }) {
  return <ProfileContent profileId={params.id} />
}

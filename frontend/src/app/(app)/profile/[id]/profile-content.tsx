'use client'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/use-auth'
import { getInitials } from '@/lib/utils'
import { Camera, Mail, CalendarDays, Briefcase, Activity, Users } from 'lucide-react'
import type { UserRole } from '@/types'

// Fields that will be sourced from the backend once a /api/users/:id/ endpoint
// is added. For now they are placeholders — functionality is not yet activated.
interface ProfileData {
  id: string
  first_name: string
  last_name: string
  email: string
  role: UserRole
  date_joined?: string
  // Future fields (not in DB yet)
  avatar_url?: string | null
  bio?: string | null
  status?: 'active' | 'away' | 'offline'
  job_title?: string | null
}

function StatusDot({ status }: { status: ProfileData['status'] }) {
  const map = {
    active: 'bg-green-500',
    away: 'bg-yellow-400',
    offline: 'bg-muted-foreground',
  }
  return (
    <span
      className={`inline-block h-2.5 w-2.5 rounded-full ${map[status ?? 'active']}`}
      aria-label={status ?? 'active'}
    />
  )
}

function ProfileAvatar({ profile }: { profile: ProfileData }) {
  return (
    <div className="relative inline-block">
      <div className="h-24 w-24 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-2xl font-bold">
        {profile.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={profile.avatar_url}
            alt={`${profile.first_name} ${profile.last_name}`}
            className="h-24 w-24 rounded-full object-cover"
          />
        ) : (
          getInitials(profile.first_name, profile.last_name)
        )}
      </div>
      {/* Upload button — visible but disabled until feature is activated */}
      <button
        disabled
        className="absolute bottom-0 right-0 h-7 w-7 rounded-full bg-background border flex items-center justify-center text-muted-foreground cursor-not-allowed opacity-60"
        title="Photo upload coming soon"
        aria-label="Upload profile photo (not yet available)"
      >
        <Camera className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-4 rounded-lg border bg-muted/30 gap-1">
      <span className="text-xl font-bold text-muted-foreground">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

/** Shown when a profile cannot be loaded (e.g. API endpoint not yet available). */
function ProfileUnavailable() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center gap-3">
      <Users className="h-12 w-12 text-muted-foreground opacity-40" />
      <h2 className="text-lg font-semibold">Profile not available</h2>
      <p className="text-sm text-muted-foreground max-w-xs">
        Viewing other users&#39; profiles will be available once the feature is fully activated.
      </p>
    </div>
  )
}

interface ProfileContentProps {
  profileId: string
}

export function ProfileContent({ profileId }: ProfileContentProps) {
  const { user } = useAuth()

  // Only the current user's own profile can be shown at this stage.
  // When GET /api/users/:id/ is implemented, replace this with a real fetch.
  const isOwnProfile = user?.id === profileId

  if (!user || !isOwnProfile) {
    return <ProfileUnavailable />
  }

  const profile: ProfileData = {
    ...user,
    // Placeholders for fields not yet in the data model
    avatar_url: null,
    bio: null,
    status: 'active',
    job_title: null,
  }

  const formattedJoined =
    (profile as ProfileData & { date_joined?: string }).date_joined
      ? new Date((profile as ProfileData & { date_joined?: string }).date_joined!).toLocaleDateString(
          'en-GB',
          { month: 'long', year: 'numeric' }
        )
      : '—'

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header card */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-6 items-start">
            <ProfileAvatar profile={profile} />

            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold">
                  {profile.first_name} {profile.last_name}
                </h1>
                <Badge variant="outline" className="capitalize">
                  {profile.role.replace('_', ' ')}
                </Badge>
              </div>

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <StatusDot status={profile.status} />
                <span className="capitalize">{profile.status ?? 'Active'}</span>
              </div>

              {profile.job_title ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Briefcase className="h-4 w-4 shrink-0" />
                  {profile.job_title}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground italic">No job title set</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">About</CardTitle>
        </CardHeader>
        <CardContent>
          {profile.bio ? (
            <p className="text-sm">{profile.bio}</p>
          ) : (
            <p className="text-sm text-muted-foreground italic">No description added yet.</p>
          )}
        </CardContent>
      </Card>

      {/* Contact & details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <Mail className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span>{profile.email}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span>Member since {formattedJoined}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Activity className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="capitalize text-muted-foreground">
              {profile.role.replace('_', ' ')} account
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Stats — placeholders until project/contract counts are wired up */}
      <div>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
          Activity
        </h2>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Projects" value="—" />
          <StatCard label="Contracts" value="—" />
          <StatCard label="Messages" value="—" />
        </div>
      </div>
    </div>
  )
}

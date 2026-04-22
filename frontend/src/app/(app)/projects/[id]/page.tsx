'use client'

import React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { MessageSquare, FileText, Calendar, Mail, Users, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { NotificationFeed } from '@/components/dashboard/notification-feed'
import { FeatureFeedback } from '@/components/feedback/feature-feedback'
import { useProject, useProjectContract, useProjectMembers, useContractRequests } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES } from '@/lib/constants'
import { formatDate, formatDateTime } from '@/lib/utils'

export default function ProjectOverviewPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const { data: project } = useProject(id)
  const { data: contractData } = useProjectContract(id)
  const { data: membersData } = useProjectMembers(id)
  const { data: requestsData } = useContractRequests(id)

  const contract = contractData?.results?.[0]
  const memberCount = membersData?.count ?? 0
  const pendingRequests = (requestsData?.results ?? []).filter((r) => r.status === 'pending').length

  // A manager who created a project and kept it assigned to themselves has no
  // counterparty to raise contract requests, so hide the review panel. It
  // reappears as soon as the project is assigned to a different user.
  const isManagerSelfOwned =
    user?.role === 'manager' &&
    !!project?.account_subscriber_id &&
    project.account_subscriber_id === user.id

  const quickLinks = [
    {
      label: 'Chat',
      description: 'Real-time project conversation',
      href: ROUTES.PROJECT_CHAT(id),
      icon: MessageSquare,
      color: 'bg-blue-100 text-blue-700',
    },
    {
      label: 'Contract',
      description: 'View and manage contracts',
      href: ROUTES.PROJECT_CONTRACT(id),
      icon: FileText,
      color: 'bg-green-100 text-green-700',
    },
    {
      label: 'Timeline',
      description: 'Project milestones and schedule',
      href: ROUTES.PROJECT_TIMELINE(id),
      icon: Calendar,
      color: 'bg-purple-100 text-purple-700',
    },
    {
      label: 'Email Organiser',
      description: 'Manage project emails and responses',
      href: ROUTES.EMAIL_ORGANISER(id),
      icon: Mail,
      color: 'bg-orange-100 text-orange-700',
    },
  ]

  return (
    <div className="space-y-6">
      {/* Quick stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xl font-bold">{memberCount}</p>
                <p className="text-xs text-muted-foreground">Members</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xl font-bold capitalize">
                  {contract?.status ?? '—'}
                </p>
                <p className="text-xs text-muted-foreground">Contract</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xl font-bold">{pendingRequests}</p>
                <p className="text-xs text-muted-foreground">Pending Requests</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Project notifications feed */}
      <NotificationFeed projectId={id} />

      {/* Quick links */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Project Sections</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {quickLinks.map((link) => {
            const Icon = link.icon
            return (
              <Link key={link.href} href={link.href}>
                <Card className="group hover:shadow-md transition-shadow cursor-pointer">
                  <CardContent className="pt-5 pb-5">
                    <div className="flex items-center gap-4">
                      <div className={`rounded-lg p-2.5 ${link.color}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-semibold group-hover:text-primary transition-colors">
                          {link.label}
                        </p>
                        <p className="text-xs text-muted-foreground">{link.description}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      </div>

      {/* Contract request section (manager only, and only when the project
          is assigned to another user — a manager doesn't review their own). */}
      {user?.role === 'manager' && !isManagerSelfOwned && pendingRequests > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Pending Contract Requests
              <Badge variant="warning">{pendingRequests}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(requestsData?.results ?? [])
                .filter((r) => r.status === 'pending')
                .map((req) => (
                  <div key={req.id} className="flex items-center justify-between p-3 border rounded-md">
                    <div>
                      <p className="text-sm">{req.description}</p>
                      <p className="text-xs text-muted-foreground">{formatDateTime(req.created_at)}</p>
                    </div>
                    <Link href={ROUTES.PROJECT_CHANGE_REQUESTS(id)}>
                      <Button size="sm" variant="outline">Review</Button>
                    </Link>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Project info */}
      {project && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Project Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <dt className="text-muted-foreground">Created</dt>
              <dd>{formatDate(project.created_at)}</dd>
              <dt className="text-muted-foreground">Last updated</dt>
              <dd>{formatDate(project.updated_at)}</dd>
              <dt className="text-muted-foreground">Project email</dt>
              <dd className="font-mono text-xs break-all">
                {project.generic_email || '—'}
              </dd>
            </dl>
          </CardContent>
        </Card>
      )}

      <FeatureFeedback
        featureKey="projects.overview"
        projectId={id}
        label="How's this project overview?"
      />
    </div>
  )
}

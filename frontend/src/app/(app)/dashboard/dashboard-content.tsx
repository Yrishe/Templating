'use client'

import React from 'react'
import Link from 'next/link'
import { PlusCircle, FolderOpen, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { NotificationFeed } from '@/components/dashboard/notification-feed'
import { ProjectSummaryCard } from '@/components/dashboard/project-summary-card'
import { useDashboard } from '@/hooks/use-notifications'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES } from '@/lib/constants'

export function DashboardContent() {
  const { user } = useAuth()
  const { data, isLoading } = useDashboard()

  const projects = data?.recent_projects ?? []
  const notifications = data?.recent_notifications ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            Welcome back{user ? `, ${user.first_name}` : ''}
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Here&apos;s what&apos;s happening across your projects.
          </p>
        </div>
        {(user?.role === 'manager' || user?.role === 'subscriber') && (
          <Link href={ROUTES.NEW_PROJECT}>
            <Button size="sm">
              <PlusCircle className="h-4 w-4 mr-2" />
              New Project
            </Button>
          </Link>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-primary/10 p-2">
                <FolderOpen className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold">{isLoading ? '—' : projects.length}</p>
                <p className="text-xs text-muted-foreground">Active Projects</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-yellow-100 p-2">
                <FileText className="h-5 w-5 text-yellow-700" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {isLoading ? '—' : data?.pending_contract_requests ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">Pending Requests</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-blue-100 p-2">
                <FileText className="h-5 w-5 text-blue-700" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {isLoading ? '—' : data?.unread_notification_count ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">Unread Notifications</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projects */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent Projects</h2>
            <Link href={ROUTES.PROJECTS} className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>

          {isLoading && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-36 rounded-lg bg-muted animate-pulse" />
              ))}
            </div>
          )}

          {!isLoading && projects.length === 0 && (
            <div className="text-center py-12 border-2 border-dashed rounded-lg">
              <FolderOpen className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
              <p className="text-sm text-muted-foreground">No projects yet</p>
              {(user?.role === 'manager' || user?.role === 'subscriber') && (
                <Link href={ROUTES.NEW_PROJECT}>
                  <Button variant="outline" size="sm" className="mt-3">
                    Create your first project
                  </Button>
                </Link>
              )}
            </div>
          )}

          {!isLoading && projects.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {projects.slice(0, 4).map((project) => (
                <ProjectSummaryCard key={project.id} project={project} />
              ))}
            </div>
          )}

        </div>

        {/* Notifications */}
        <div>
          <NotificationFeed />
        </div>
      </div>
    </div>
  )
}

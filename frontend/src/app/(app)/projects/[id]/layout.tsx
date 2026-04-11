'use client'

import React from 'react'
import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { MessageSquare, FileText, FilePen, Calendar, LayoutDashboard, UserPlus, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProject } from '@/hooks/use-projects'
import { ROUTES } from '@/lib/constants'

const projectTabs = [
  { label: 'Overview', href: (id: string) => ROUTES.PROJECT(id), icon: LayoutDashboard },
  { label: 'Chat', href: (id: string) => ROUTES.PROJECT_CHAT(id), icon: MessageSquare },
  { label: 'Contract', href: (id: string) => ROUTES.PROJECT_CONTRACT(id), icon: FileText },
  // Dedicated history view for contract change requests — shows pending
  // rows for the manager to approve/reject and the full audit trail
  // (approved, rejected, pending) for everyone.
  { label: 'Change Requests', href: (id: string) => ROUTES.PROJECT_CHANGE_REQUESTS(id), icon: FilePen },
  { label: 'Timeline', href: (id: string) => ROUTES.PROJECT_TIMELINE(id), icon: Calendar },
  // Invite additional members post-creation. Server-side the endpoint is
  // gated to manager OR the project's account owner, so invited_account
  // users hitting this page will get a 403 on submit.
  { label: 'Invite', href: (id: string) => ROUTES.PROJECT_INVITE(id), icon: UserPlus },
]

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>()
  const pathname = usePathname()
  const { data: project, isLoading } = useProject(id)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          href={ROUTES.PROJECTS}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-3"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          All Projects
        </Link>
        <h1 className="text-2xl font-bold truncate">
          {isLoading ? (
            <span className="inline-block h-7 w-48 rounded bg-muted animate-pulse" />
          ) : (
            project?.name ?? 'Project'
          )}
        </h1>
        {project?.description && (
          <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{project.description}</p>
        )}
      </div>

      {/* Tab navigation — pill-shaped tabs on a glass strip instead of the
          old flat underline. Active tab gets the primary gradient used by
          the sidebar, so the nav system feels consistent. */}
      <nav
        className="flex gap-1 p-1 rounded-xl border border-white/70 bg-white/70 backdrop-blur-md [box-shadow:var(--shadow-soft)] dark:border-white/10 dark:bg-slate-900/60 overflow-x-auto"
        aria-label="Project sections"
      >
        {projectTabs.map((tab) => {
          const href = tab.href(id)
          const isActive = pathname === href
          const Icon = tab.icon
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg transition-all duration-150 whitespace-nowrap',
                isActive
                  ? 'bg-gradient-to-r from-primary to-primary/85 text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-white/80 hover:text-foreground dark:hover:bg-white/5'
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </Link>
          )
        })}
      </nav>

      {children}
    </div>
  )
}

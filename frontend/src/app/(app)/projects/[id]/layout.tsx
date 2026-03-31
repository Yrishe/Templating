'use client'

import React from 'react'
import Link from 'next/link'
import { useParams, usePathname } from 'next/navigation'
import { MessageSquare, FileText, Calendar, LayoutDashboard, ArrowLeft } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useProject } from '@/hooks/use-projects'
import { ROUTES } from '@/lib/constants'

const projectTabs = [
  { label: 'Overview', href: (id: string) => ROUTES.PROJECT(id), icon: LayoutDashboard },
  { label: 'Chat', href: (id: string) => ROUTES.PROJECT_CHAT(id), icon: MessageSquare },
  { label: 'Contract', href: (id: string) => ROUTES.PROJECT_CONTRACT(id), icon: FileText },
  { label: 'Timeline', href: (id: string) => ROUTES.PROJECT_TIMELINE(id), icon: Calendar },
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

      {/* Tab navigation */}
      <nav className="flex gap-1 border-b" aria-label="Project sections">
        {projectTabs.map((tab) => {
          const href = tab.href(id)
          const isActive = pathname === href
          const Icon = tab.icon
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
                isActive
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
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

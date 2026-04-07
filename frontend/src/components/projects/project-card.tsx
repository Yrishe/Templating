'use client'

import React from 'react'
import Link from 'next/link'
import { FolderOpen, Calendar, Mail, MessageSquare, FileText, Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'
import { formatDate } from '@/lib/utils'
import type { Project } from '@/types'

interface ProjectCardProps {
  project: Project
  onDelete?: (id: string) => void
  showDelete?: boolean
}

export function ProjectCard({ project, onDelete, showDelete }: ProjectCardProps) {
  return (
    <Card className="flex flex-col hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-primary/10 p-2 shrink-0">
            <FolderOpen className="h-5 w-5 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold leading-tight truncate">{project.name}</h3>
            {project.description && (
              <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                {project.description}
              </p>
            )}
            {project.tags && project.tags.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {project.tags.map((tag) => (
                  <span
                    key={tag.id}
                    className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium border"
                    style={{
                      borderColor: tag.color,
                      color: tag.color,
                      backgroundColor: `${tag.color}15`,
                    }}
                  >
                    {tag.name}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 pb-3">
        <div className="space-y-2">
          {project.generic_email && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Mail className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{project.generic_email}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            <span>Created {formatDate(project.created_at)}</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5 shrink-0" />
            <span>Updated {formatDate(project.updated_at)}</span>
          </div>
        </div>
      </CardContent>

      <CardFooter className="flex flex-wrap gap-2 pt-3">
        <Link href={ROUTES.PROJECT(project.id)} className="flex-1">
          <Button variant="default" size="sm" className="w-full">
            Open
          </Button>
        </Link>
        <Link href={ROUTES.PROJECT_CHAT(project.id)}>
          <Button variant="outline" size="sm" aria-label="Chat">
            <MessageSquare className="h-4 w-4" />
          </Button>
        </Link>
        <Link href={ROUTES.PROJECT_CONTRACT(project.id)}>
          <Button variant="outline" size="sm" aria-label="Contract">
            <FileText className="h-4 w-4" />
          </Button>
        </Link>
        {showDelete && onDelete && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => onDelete(project.id)}
            aria-label="Delete project"
          >
            Delete
          </Button>
        )}
      </CardFooter>
    </Card>
  )
}

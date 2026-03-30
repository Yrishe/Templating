'use client'

import React from 'react'
import Link from 'next/link'
import { ArrowRight, FolderOpen, Calendar } from 'lucide-react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/constants'
import { formatDate, truncate } from '@/lib/utils'
import type { Project } from '@/types'

interface ProjectSummaryCardProps {
  project: Project
}

export function ProjectSummaryCard({ project }: ProjectSummaryCardProps) {
  return (
    <Card className="group hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="shrink-0 rounded-md bg-primary/10 p-1.5">
              <FolderOpen className="h-4 w-4 text-primary" />
            </div>
            <h3 className="font-semibold text-sm truncate">{project.name}</h3>
          </div>
          <Badge variant="outline" className="shrink-0 text-[10px]">
            Active
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pb-3">
        {project.description && (
          <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
            {truncate(project.description, 120)}
          </p>
        )}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-3">
          <Calendar className="h-3.5 w-3.5" />
          <span>{formatDate(project.created_at)}</span>
        </div>
        <Link href={ROUTES.PROJECT(project.id)}>
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs group-hover:bg-primary group-hover:text-primary-foreground transition-colors"
          >
            View Project
            <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
          </Button>
        </Link>
      </CardContent>
    </Card>
  )
}

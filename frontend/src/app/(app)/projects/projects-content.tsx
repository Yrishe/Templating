'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { PlusCircle, Search, FolderOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ProjectCard } from '@/components/projects/project-card'
import { useProjects, useDeleteProject } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES } from '@/lib/constants'

export function ProjectsContent() {
  const { user } = useAuth()
  const { data, isLoading, isError } = useProjects()
  const deleteProject = useDeleteProject()
  const [search, setSearch] = useState('')

  const projects = (data?.results ?? []).filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  const canCreate = user?.role === 'manager' || user?.role === 'subscriber'
  const canDelete = user?.role === 'manager'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-bold">Projects</h1>
        {canCreate && (
          <Link href={ROUTES.NEW_PROJECT}>
            <Button size="sm">
              <PlusCircle className="h-4 w-4 mr-2" />
              New Project
            </Button>
          </Link>
        )}
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search projects..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9 max-w-sm"
          aria-label="Search projects"
        />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-48 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-destructive text-sm">Failed to load projects. Please try again.</p>
      )}

      {!isLoading && !isError && projects.length === 0 && (
        <div className="text-center py-16 border-2 border-dashed rounded-lg">
          <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-50" />
          <h3 className="font-semibold mb-1">
            {search ? 'No projects match your search' : 'No projects yet'}
          </h3>
          {!search && canCreate && (
            <Link href={ROUTES.NEW_PROJECT}>
              <Button variant="outline" size="sm" className="mt-3">
                Create your first project
              </Button>
            </Link>
          )}
        </div>
      )}

      {!isLoading && !isError && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              showDelete={canDelete}
              onDelete={(id) => deleteProject.mutate(id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

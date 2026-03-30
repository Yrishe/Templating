'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useCreateProject } from '@/hooks/use-projects'
import { ROUTES } from '@/lib/constants'

const createProjectSchema = z.object({
  name: z.string().min(2, 'Project name must be at least 2 characters').max(100),
  description: z.string().max(500).optional(),
  generic_email: z.string().email('Please enter a valid email address'),
})

type CreateProjectFormData = z.infer<typeof createProjectSchema>

export function CreateProjectForm() {
  const router = useRouter()
  const createProject = useCreateProject()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
  })

  const onSubmit = async (data: CreateProjectFormData) => {
    try {
      const project = await createProject.mutateAsync(data)
      router.push(ROUTES.PROJECT(project.id))
    } catch (err) {
      // error handled by mutation state
    }
  }

  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>Create New Project</CardTitle>
        <CardDescription>
          Set up a new contract management project with its own chat, contract, and timeline.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="name">Project Name *</Label>
            <Input
              id="name"
              placeholder="e.g. Q3 Vendor Agreement"
              {...register('name')}
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <p className="text-sm text-destructive">{errors.name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <textarea
              id="description"
              placeholder="Describe the purpose of this project..."
              className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
              {...register('description')}
            />
            {errors.description && (
              <p className="text-sm text-destructive">{errors.description.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="generic_email">Generic Email Address *</Label>
            <Input
              id="generic_email"
              type="email"
              placeholder="project@company.com"
              {...register('generic_email')}
              aria-invalid={!!errors.generic_email}
            />
            <p className="text-xs text-muted-foreground">
              This email will be used for automated communications related to this project.
            </p>
            {errors.generic_email && (
              <p className="text-sm text-destructive">{errors.generic_email.message}</p>
            )}
          </div>

          {createProject.isError && (
            <p className="text-sm text-destructive">
              {(createProject.error as Error).message || 'Failed to create project. Please try again.'}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => router.back()}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || createProject.isPending}>
              {createProject.isPending ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

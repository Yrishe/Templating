'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useCreateProject, useTags, useCreateTag } from '@/hooks/use-projects'
import { ROUTES } from '@/lib/constants'
import type { Tag } from '@/types'

// Email is no longer collected — the backend auto-generates an inbound mailbox
// for each project (proj-<uuid8>@inbound.contractmgr.app).
const createProjectSchema = z.object({
  name: z.string().min(2, 'Project name must be at least 2 characters').max(100),
  description: z.string().max(500).optional(),
})

type CreateProjectFormData = z.infer<typeof createProjectSchema>

const DEFAULT_NEW_TAG_COLOR = '#6B7280'

export function CreateProjectForm() {
  const router = useRouter()
  const createProject = useCreateProject()
  const { data: existingTags } = useTags()
  const createTag = useCreateTag()

  const [selectedTagIds, setSelectedTagIds] = React.useState<string[]>([])
  const [newTagName, setNewTagName] = React.useState('')
  const [newTagColor, setNewTagColor] = React.useState(DEFAULT_NEW_TAG_COLOR)
  const [tagError, setTagError] = React.useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateProjectFormData>({
    resolver: zodResolver(createProjectSchema),
  })

  const toggleTag = (id: string) => {
    setSelectedTagIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    )
  }

  const handleAddNewTag = async () => {
    setTagError(null)
    const name = newTagName.trim()
    if (!name) return
    try {
      const tag = await createTag.mutateAsync({ name, color: newTagColor })
      setSelectedTagIds((prev) => [...prev, tag.id])
      setNewTagName('')
      setNewTagColor(DEFAULT_NEW_TAG_COLOR)
    } catch (err) {
      setTagError((err as Error).message || 'Failed to create tag')
    }
  }

  const onSubmit = async (data: CreateProjectFormData) => {
    try {
      const project = await createProject.mutateAsync({
        ...data,
        tag_ids: selectedTagIds,
      })
      router.push(ROUTES.PROJECT(project.id))
    } catch {
      // error surfaced via createProject.error below
    }
  }

  return (
    <Card className="max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>Create New Project</CardTitle>
        <CardDescription>
          Set up a new contract management project with its own chat, contract, timeline,
          and auto-generated inbound email address.
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

          {/* ─── Tags ────────────────────────────────────────────────── */}
          <div className="space-y-3">
            <Label>Tags</Label>
            <p className="text-xs text-muted-foreground">
              Attach existing tags (e.g. priority labels) or create new ones.
            </p>

            {/* Existing tags as toggleable chips */}
            {existingTags && existingTags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {existingTags.map((tag: Tag) => {
                  const isSelected = selectedTagIds.includes(tag.id)
                  return (
                    <button
                      type="button"
                      key={tag.id}
                      onClick={() => toggleTag(tag.id)}
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border transition-colors ${
                        isSelected
                          ? 'border-primary bg-primary/10'
                          : 'border-input hover:bg-accent'
                      }`}
                    >
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ backgroundColor: tag.color }}
                      />
                      {tag.name}
                      {isSelected && <X className="h-3 w-3" />}
                    </button>
                  )
                })}
              </div>
            )}

            {/* New tag inline creator */}
            <div className="flex items-center gap-2">
              <Input
                placeholder="New tag name..."
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                className="flex-1"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAddNewTag()
                  }
                }}
              />
              <input
                type="color"
                value={newTagColor}
                onChange={(e) => setNewTagColor(e.target.value)}
                className="h-10 w-12 rounded-md border border-input cursor-pointer"
                aria-label="Tag colour"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddNewTag}
                disabled={!newTagName.trim() || createTag.isPending}
              >
                <Plus className="h-4 w-4 mr-1" />
                Add
              </Button>
            </div>
            {tagError && <p className="text-sm text-destructive">{tagError}</p>}
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

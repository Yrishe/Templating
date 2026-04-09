'use client'

import React from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { X, Plus, Users, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useCreateProject, useTags, useCreateTag, useDeleteTag } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { api } from '@/lib/api'
import { ROUTES } from '@/lib/constants'
import type { Tag, User } from '@/types'

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
  const { user: currentUser } = useAuth()
  const isManager = currentUser?.role === 'manager'
  const createProject = useCreateProject()
  const { data: existingTags } = useTags()
  const createTag = useCreateTag()
  const deleteTag = useDeleteTag()

  // ─── Owner (manager-only) ──────────────────────────────────────────────
  const [ownerMode, setOwnerMode] = React.useState<'self' | 'other'>('self')
  const [ownerQuery, setOwnerQuery] = React.useState('')
  const [ownerResults, setOwnerResults] = React.useState<User[]>([])
  const [ownerUser, setOwnerUser] = React.useState<User | null>(null)
  const [ownerSearching, setOwnerSearching] = React.useState(false)

  React.useEffect(() => {
    if (!isManager || ownerMode !== 'other') {
      setOwnerResults([])
      return
    }
    const q = ownerQuery.trim()
    if (!q) {
      setOwnerResults([])
      return
    }
    let cancelled = false
    setOwnerSearching(true)
    const t = setTimeout(() => {
      api
        .get<User[]>(`/api/auth/users/search/?role=account&q=${encodeURIComponent(q)}`)
        .then((res) => {
          if (!cancelled) setOwnerResults(res)
        })
        .catch(() => {
          if (!cancelled) setOwnerResults([])
        })
        .finally(() => {
          if (!cancelled) setOwnerSearching(false)
        })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [isManager, ownerMode, ownerQuery])

  const [selectedTagIds, setSelectedTagIds] = React.useState<string[]>([])
  const [newTagName, setNewTagName] = React.useState('')
  const [newTagColor, setNewTagColor] = React.useState(DEFAULT_NEW_TAG_COLOR)
  const [tagError, setTagError] = React.useState<string | null>(null)

  // ─── Invite members ────────────────────────────────────────────────────
  const [memberQuery, setMemberQuery] = React.useState('')
  const [memberResults, setMemberResults] = React.useState<User[]>([])
  const [selectedMembers, setSelectedMembers] = React.useState<User[]>([])
  const [memberSearching, setMemberSearching] = React.useState(false)

  React.useEffect(() => {
    const q = memberQuery.trim()
    if (!q) {
      setMemberResults([])
      return
    }
    let cancelled = false
    setMemberSearching(true)
    const t = setTimeout(() => {
      api
        .get<User[]>(`/api/auth/users/search/?q=${encodeURIComponent(q)}`)
        .then((res) => {
          if (!cancelled) setMemberResults(res)
        })
        .catch(() => {
          if (!cancelled) setMemberResults([])
        })
        .finally(() => {
          if (!cancelled) setMemberSearching(false)
        })
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(t)
    }
  }, [memberQuery])

  const toggleMember = (user: User) => {
    setSelectedMembers((prev) =>
      prev.find((m) => m.id === user.id)
        ? prev.filter((m) => m.id !== user.id)
        : [...prev, user]
    )
  }

  const removeMember = (id: string) => {
    setSelectedMembers((prev) => prev.filter((m) => m.id !== id))
  }

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
        ...(isManager && ownerMode === 'other' && ownerUser
          ? { owner_user_id: ownerUser.id }
          : {}),
      })
      // Invite the selected members — best effort, don't block navigation on failure.
      await Promise.all(
        selectedMembers.map((m) =>
          api
            .post(`/api/projects/${project.id}/members/`, { user_id: m.id })
            .catch(() => null)
        )
      )
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

          {/* ─── Owner (manager-only) ───────────────────────────────── */}
          {isManager && (
            <div className="space-y-3">
              <Label>Project Owner</Label>
              <p className="text-xs text-muted-foreground">
                As a manager you can keep ownership yourself or assign the project
                to an existing Account user.
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={ownerMode === 'self' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setOwnerMode('self')
                    setOwnerUser(null)
                  }}
                >
                  Assign to me
                </Button>
                <Button
                  type="button"
                  variant={ownerMode === 'other' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setOwnerMode('other')}
                >
                  Assign to an Account
                </Button>
              </div>

              {ownerMode === 'other' && (
                <div className="space-y-2">
                  <div className="relative">
                    <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search Account by name or email..."
                      value={ownerQuery}
                      onChange={(e) => setOwnerQuery(e.target.value)}
                      className="pl-8"
                    />
                  </div>
                  {ownerUser ? (
                    <div className="inline-flex items-center gap-2 rounded-full bg-secondary px-3 py-1 text-xs">
                      <span className="font-medium">
                        {ownerUser.first_name || ownerUser.email}
                      </span>
                      <span className="text-muted-foreground">{ownerUser.email}</span>
                      <button
                        type="button"
                        onClick={() => setOwnerUser(null)}
                        aria-label="Clear owner"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  ) : (
                    ownerQuery.trim() && (
                      <div className="border rounded-md max-h-40 overflow-y-auto divide-y">
                        {ownerSearching && (
                          <p className="p-2 text-xs text-muted-foreground">Searching...</p>
                        )}
                        {!ownerSearching && ownerResults.length === 0 && (
                          <p className="p-2 text-xs text-muted-foreground">
                            No matching Account users.
                          </p>
                        )}
                        {ownerResults.map((u) => (
                          <button
                            type="button"
                            key={u.id}
                            onClick={() => {
                              setOwnerUser(u)
                              setOwnerQuery('')
                            }}
                            className="w-full text-left p-2 text-sm hover:bg-accent"
                          >
                            <div className="font-medium">
                              {u.first_name || u.last_name
                                ? `${u.first_name} ${u.last_name}`.trim()
                                : u.email}
                            </div>
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                          </button>
                        ))}
                      </div>
                    )
                  )}
                </div>
              )}
            </div>
          )}

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
                    <span
                      key={tag.id}
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border transition-colors ${
                        isSelected
                          ? 'border-primary bg-primary/10'
                          : 'border-input hover:bg-accent'
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => toggleTag(tag.id)}
                        className="inline-flex items-center gap-1.5"
                        aria-pressed={isSelected}
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: tag.color }}
                        />
                        {tag.name}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (
                            confirm(`Delete tag "${tag.name}"? This removes it from all projects.`)
                          ) {
                            setSelectedTagIds((prev) => prev.filter((id) => id !== tag.id))
                            deleteTag.mutate(tag.id)
                          }
                        }}
                        className="text-muted-foreground hover:text-destructive"
                        aria-label={`Delete tag ${tag.name}`}
                        title="Delete tag"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
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

          {/* ─── Invite members ──────────────────────────────────────── */}
          <div className="space-y-3">
            <Label className="flex items-center gap-1.5">
              <Users className="h-4 w-4" />
              Invite team members
            </Label>
            <p className="text-xs text-muted-foreground">
              Search registered accounts by name or email and invite them to this project.
            </p>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or email..."
                value={memberQuery}
                onChange={(e) => setMemberQuery(e.target.value)}
                className="pl-8"
              />
            </div>

            {memberQuery.trim() && (
              <div className="border rounded-md max-h-48 overflow-y-auto divide-y">
                {memberSearching && (
                  <p className="p-2 text-xs text-muted-foreground">Searching...</p>
                )}
                {!memberSearching && memberResults.length === 0 && (
                  <p className="p-2 text-xs text-muted-foreground">No matching accounts.</p>
                )}
                {memberResults.map((u) => {
                  const selected = !!selectedMembers.find((m) => m.id === u.id)
                  return (
                    <button
                      type="button"
                      key={u.id}
                      onClick={() => toggleMember(u)}
                      className={`w-full text-left p-2 text-sm flex items-center justify-between hover:bg-accent ${
                        selected ? 'bg-primary/5' : ''
                      }`}
                    >
                      <div>
                        <div className="font-medium">
                          {u.first_name || u.last_name
                            ? `${u.first_name} ${u.last_name}`.trim()
                            : u.email}
                        </div>
                        <div className="text-xs text-muted-foreground">{u.email}</div>
                      </div>
                      {selected ? (
                        <X className="h-4 w-4" />
                      ) : (
                        <Plus className="h-4 w-4" />
                      )}
                    </button>
                  )
                })}
              </div>
            )}

            {selectedMembers.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedMembers.map((m) => (
                  <span
                    key={m.id}
                    className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium"
                  >
                    {m.first_name || m.email}
                    <button
                      type="button"
                      onClick={() => removeMember(m.id)}
                      aria-label={`Remove ${m.email}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
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

'use client'

import React, { useState } from 'react'
import {
  Calendar,
  CheckCircle2,
  Circle,
  Clock,
  Plus,
  AlertTriangle,
  Pencil,
  Trash2,
  MessageSquare,
  Send,
  ChevronDown,
  ChevronUp,
  Bell,
  Flag,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  useProjectTimeline,
  useCreateTimelineEvent,
  useUpdateTimelineEvent,
  useDeleteTimelineEvent,
  useCreateTimelineComment,
  useProject,
} from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import type { TimelineEvent, TimelineComment, TimelineEventPriority, TimelineCommentType } from '@/types'

// ─── Status helpers ──────────────────────────────────────────────────

function EventStatusIcon({ status }: { status: TimelineEvent['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />
    case 'in_progress':
      return <Clock className="h-4 w-4 text-blue-500" />
    case 'planned':
      return <Circle className="h-4 w-4 text-muted-foreground" />
  }
}

function EventStatusBadge({ status }: { status: TimelineEvent['status'] }) {
  const config = {
    planned: { variant: 'outline' as const, label: 'Planned' },
    in_progress: { variant: 'info' as const, label: 'In Progress' },
    completed: { variant: 'success' as const, label: 'Completed' },
  }[status]
  return <Badge variant={config.variant}>{config.label}</Badge>
}

function PriorityBadge({ priority }: { priority: TimelineEventPriority }) {
  const config: Record<TimelineEventPriority, { variant: 'outline' | 'info' | 'warning' | 'destructive'; label: string }> = {
    low: { variant: 'outline', label: 'Low' },
    medium: { variant: 'info', label: 'Medium' },
    high: { variant: 'warning', label: 'High' },
    critical: { variant: 'destructive', label: 'Critical' },
  }
  const c = config[priority]
  return (
    <Badge variant={c.variant} className="gap-1">
      <Flag className="h-3 w-3" />
      {c.label}
    </Badge>
  )
}

function CommentTypeBadge({ type }: { type: TimelineCommentType }) {
  const labels: Record<TimelineCommentType, string> = {
    general: 'General',
    completion_confirmation: 'Confirmed',
    status_update: 'Status Update',
    feedback: 'Feedback',
    suggestion: 'Suggestion',
  }
  const variants: Record<TimelineCommentType, 'outline' | 'success' | 'info' | 'warning'> = {
    general: 'outline',
    completion_confirmation: 'success',
    status_update: 'info',
    feedback: 'warning',
    suggestion: 'info',
  }
  return <Badge variant={variants[type]} className="text-[10px] px-1.5 py-0">{labels[type]}</Badge>
}

// ─── Event form (create / edit) ──────────────────────────────────────

interface EventFormProps {
  projectId: string
  event?: TimelineEvent
  onClose: () => void
}

function EventForm({ projectId, event, onClose }: EventFormProps) {
  const [title, setTitle] = useState(event?.title ?? '')
  const [description, setDescription] = useState(event?.description ?? '')
  const [startDate, setStartDate] = useState(event?.start_date ?? '')
  const [endDate, setEndDate] = useState(event?.end_date ?? '')
  const [status, setStatus] = useState<TimelineEvent['status']>(event?.status ?? 'planned')
  const [priority, setPriority] = useState<TimelineEventPriority>(event?.priority ?? 'medium')
  const [reminderDays, setReminderDays] = useState(String(event?.deadline_reminder_days ?? 3))

  const createEvent = useCreateTimelineEvent()
  const updateEvent = useUpdateTimelineEvent(projectId)
  const isEditing = Boolean(event)
  const isPending = createEvent.isPending || updateEvent.isPending

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !startDate) return

    const payload = {
      title,
      description,
      start_date: startDate,
      end_date: endDate || null,
      status,
      priority,
      deadline_reminder_days: parseInt(reminderDays, 10) || 3,
    }

    if (isEditing && event) {
      await updateEvent.mutateAsync({ eventId: event.id, ...payload })
    } else {
      await createEvent.mutateAsync({ projectId, ...payload })
    }
    onClose()
  }

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">
          {isEditing ? 'Edit Timeline Event' : 'Add Timeline Event'}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-title">Title *</Label>
              <Input
                id="event-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Event title"
                required
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="event-desc">Description</Label>
              <textarea
                id="event-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="start-date">Start Date *</Label>
              <Input
                id="start-date"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end-date">Deadline</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-status">Status</Label>
              <select
                id="event-status"
                value={status}
                onChange={(e) => setStatus(e.target.value as TimelineEvent['status'])}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <option value="planned">Planned</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="event-priority">Priority</Label>
              <select
                id="event-priority"
                value={priority}
                onChange={(e) => setPriority(e.target.value as TimelineEventPriority)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            {endDate && (
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="reminder-days" className="flex items-center gap-1.5">
                  <Bell className="h-3.5 w-3.5" />
                  Reminder (days before deadline)
                </Label>
                <Input
                  id="reminder-days"
                  type="number"
                  min="1"
                  max="30"
                  value={reminderDays}
                  onChange={(e) => setReminderDays(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  A notification will be sent to the project panel {reminderDays} day{reminderDays !== '1' ? 's' : ''} before the deadline.
                </p>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={isPending}>
              {isPending ? 'Saving...' : isEditing ? 'Save Changes' : 'Add Event'}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ─── Comment section ─────────────────────────────────────────────────

interface CommentSectionProps {
  projectId: string
  event: TimelineEvent
}

function CommentSection({ projectId, event }: CommentSectionProps) {
  const [content, setContent] = useState('')
  const [commentType, setCommentType] = useState<TimelineCommentType>('general')
  const createComment = useCreateTimelineComment(projectId)
  const comments = event.comments ?? []

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return
    await createComment.mutateAsync({
      eventId: event.id,
      content: content.trim(),
      comment_type: commentType,
    })
    setContent('')
    setCommentType('general')
  }

  return (
    <div className="mt-3 border-t pt-3 space-y-3">
      {comments.length > 0 && (
        <div className="space-y-2">
          {comments.map((comment: TimelineComment) => (
            <div key={comment.id} className="flex gap-2 text-sm">
              <div className="h-6 w-6 rounded-full bg-muted flex items-center justify-center text-[10px] font-medium shrink-0 mt-0.5">
                {comment.author.first_name?.charAt(0) ?? ''}
                {comment.author.last_name?.charAt(0) ?? ''}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-xs">
                    {comment.author.first_name} {comment.author.last_name}
                  </span>
                  <CommentTypeBadge type={comment.comment_type} />
                  <span className="text-[10px] text-muted-foreground">
                    {formatRelativeTime(comment.created_at)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{comment.content}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2 items-end">
        <div className="flex-1 space-y-1.5">
          <select
            value={commentType}
            onChange={(e) => setCommentType(e.target.value as TimelineCommentType)}
            className="h-7 w-full rounded-md border border-input bg-background px-2 text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <option value="general">General</option>
            <option value="completion_confirmation">Confirm Completion</option>
            <option value="status_update">Status Update</option>
            <option value="feedback">Feedback</option>
            <option value="suggestion">Suggestion</option>
          </select>
          <Input
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Add a comment..."
            className="h-8 text-xs"
          />
        </div>
        <Button
          type="submit"
          size="sm"
          variant="outline"
          className="h-8 px-2"
          disabled={!content.trim() || createComment.isPending}
        >
          <Send className="h-3.5 w-3.5" />
        </Button>
      </form>
    </div>
  )
}

// ─── Single event card ───────────────────────────────────────────────

interface EventCardProps {
  event: TimelineEvent
  projectId: string
  canEdit: boolean
  onEdit: (event: TimelineEvent) => void
}

function EventCard({ event, projectId, canEdit, onEdit }: EventCardProps) {
  const [showComments, setShowComments] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const deleteEvent = useDeleteTimelineEvent(projectId)

  const isOverdue =
    event.end_date &&
    event.status !== 'completed' &&
    new Date(event.end_date) < new Date()

  const handleDelete = async () => {
    await deleteEvent.mutateAsync(event.id)
    setConfirmDelete(false)
  }

  return (
    <>
      <Card className={isOverdue ? 'border-destructive/50' : ''}>
        <CardContent className="py-4 px-4">
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="font-medium text-sm">{event.title}</h4>
              <EventStatusBadge status={event.status} />
              <PriorityBadge priority={event.priority} />
            </div>
            {canEdit && (
              <div className="flex gap-1 shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={() => onEdit(event)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </div>

          {event.description && (
            <p className="text-sm text-muted-foreground mb-2">{event.description}</p>
          )}

          <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {formatDate(event.start_date)}
            </span>
            {event.end_date && (
              <span className={isOverdue ? 'text-destructive font-medium' : ''}>
                {isOverdue ? 'Overdue: ' : 'Due: '}
                {formatDate(event.end_date)}
              </span>
            )}
            {event.end_date && (
              <span className="flex items-center gap-1">
                <Bell className="h-3 w-3" />
                Reminder: {event.deadline_reminder_days}d before
              </span>
            )}
            {event.created_by && (
              <span>
                By {event.created_by.first_name} {event.created_by.last_name}
              </span>
            )}
          </div>

          {/* Comments toggle */}
          <button
            type="button"
            onClick={() => setShowComments(!showComments)}
            className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <MessageSquare className="h-3.5 w-3.5" />
            {event.comment_count ?? 0} comment{(event.comment_count ?? 0) !== 1 ? 's' : ''}
            {showComments ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>

          {showComments && <CommentSection projectId={projectId} event={event} />}
        </CardContent>
      </Card>

      {/* Delete confirmation dialog */}
      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Event</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &ldquo;{event.title}&rdquo;? This will also
              remove all comments on this event. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              disabled={deleteEvent.isPending}
            >
              {deleteEvent.isPending ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

// ─── Main timeline view ──────────────────────────────────────────────

interface TimelineViewProps {
  projectId: string
}

export function TimelineView({ projectId }: TimelineViewProps) {
  const { user } = useAuth()
  const { data: project } = useProject(projectId)
  const { data, isLoading, isError } = useProjectTimeline(projectId)
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingEvent, setEditingEvent] = useState<TimelineEvent | null>(null)

  const isManager = user?.role === 'manager'
  const isOwner = Boolean(
    project?.account_subscriber_id && user?.id === project.account_subscriber_id
  )
  const canEdit = isManager || isOwner

  const events = (data?.events ?? []).sort(
    (a, b) => new Date(a.start_date).getTime() - new Date(b.start_date).getTime()
  )

  // Group events by status for summary
  const statusCounts = events.reduce(
    (acc, e) => {
      acc[e.status] = (acc[e.status] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-10 w-10 text-destructive mx-auto mb-3" />
        <p className="text-muted-foreground">Failed to load timeline</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Project Timeline
        </h3>
        {canEdit && !showAddForm && !editingEvent && (
          <Button size="sm" onClick={() => setShowAddForm(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add Event
          </Button>
        )}
      </div>

      {/* Summary bar */}
      {events.length > 0 && (
        <div className="flex gap-4 text-xs text-muted-foreground">
          <span>{events.length} total</span>
          {statusCounts.planned ? <span>{statusCounts.planned} planned</span> : null}
          {statusCounts.in_progress ? (
            <span className="text-blue-600">{statusCounts.in_progress} in progress</span>
          ) : null}
          {statusCounts.completed ? (
            <span className="text-green-600">{statusCounts.completed} completed</span>
          ) : null}
        </div>
      )}

      {/* Add form */}
      {showAddForm && (
        <EventForm projectId={projectId} onClose={() => setShowAddForm(false)} />
      )}

      {/* Edit form */}
      {editingEvent && (
        <EventForm
          projectId={projectId}
          event={editingEvent}
          onClose={() => setEditingEvent(null)}
        />
      )}

      {/* Empty state */}
      {events.length === 0 && !showAddForm && (
        <div className="text-center py-16 border-2 border-dashed rounded-lg">
          <Calendar className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
          <h3 className="font-medium mb-1">No timeline events yet</h3>
          <p className="text-sm text-muted-foreground">
            {canEdit
              ? 'Add the first event to get started.'
              : 'No events have been added yet.'}
          </p>
        </div>
      )}

      {/* Event list */}
      {events.length > 0 && (
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-border" />

          <div className="space-y-4">
            {events.map((event) => (
              <div key={event.id} className="relative pl-12">
                {/* Dot */}
                <div className="absolute left-3.5 -translate-x-1/2 top-3 z-10 bg-background">
                  <EventStatusIcon status={event.status} />
                </div>

                <EventCard
                  event={event}
                  projectId={projectId}
                  canEdit={canEdit}
                  onEdit={(e) => setEditingEvent(e)}
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

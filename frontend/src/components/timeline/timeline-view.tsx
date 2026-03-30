'use client'

import React, { useState } from 'react'
import { Calendar, CheckCircle2, Circle, Clock, Plus, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useProjectTimeline, useCreateTimelineEvent } from '@/hooks/use-projects'
import { useAuth } from '@/hooks/use-auth'
import { formatDate } from '@/lib/utils'
import type { TimelineEvent } from '@/types'

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

interface AddEventFormProps {
  timelineId: string
  onClose: () => void
}

function AddEventForm({ timelineId, onClose }: AddEventFormProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const createEvent = useCreateTimelineEvent()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title || !startDate) return

    await createEvent.mutateAsync({
      timeline: timelineId,
      title,
      description,
      start_date: startDate,
      end_date: endDate || null,
      status: 'planned',
    })
    onClose()
  }

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Add Timeline Event</CardTitle>
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
              <Input
                id="event-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
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
              <Label htmlFor="end-date">End Date</Label>
              <Input
                id="end-date"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={createEvent.isPending}>
              {createEvent.isPending ? 'Adding...' : 'Add Event'}
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

interface TimelineViewProps {
  projectId: string
}

export function TimelineView({ projectId }: TimelineViewProps) {
  const { user } = useAuth()
  const { data, isLoading, isError } = useProjectTimeline(projectId)
  const [showAddForm, setShowAddForm] = useState(false)
  const isManager = user?.role === 'manager'

  const events = (data?.results ?? []).sort(
    (a, b) => new Date(a.start_date).getTime() - new Date(b.start_date).getTime()
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
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Project Timeline
        </h3>
        {isManager && !showAddForm && (
          <Button size="sm" onClick={() => setShowAddForm(true)}>
            <Plus className="h-4 w-4 mr-1" />
            Add Event
          </Button>
        )}
      </div>

      {showAddForm && (
        <AddEventForm
          timelineId={projectId}
          onClose={() => setShowAddForm(false)}
        />
      )}

      {events.length === 0 && !showAddForm && (
        <div className="text-center py-16 border-2 border-dashed rounded-lg">
          <Calendar className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
          <h3 className="font-medium mb-1">No timeline events yet</h3>
          <p className="text-sm text-muted-foreground">
            {isManager ? 'Add the first event to get started.' : 'No events have been added yet.'}
          </p>
        </div>
      )}

      {events.length > 0 && (
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-border" />

          <div className="space-y-4">
            {events.map((event, index) => (
              <div key={event.id} className="relative pl-12">
                {/* Dot */}
                <div className="absolute left-3.5 -translate-x-1/2 top-3 z-10 bg-background">
                  <EventStatusIcon status={event.status} />
                </div>

                <Card className={index === events.length - 1 ? '' : ''}>
                  <CardContent className="py-4 px-4">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <h4 className="font-medium text-sm">{event.title}</h4>
                      <EventStatusBadge status={event.status} />
                    </div>
                    {event.description && (
                      <p className="text-sm text-muted-foreground mb-2">{event.description}</p>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(event.start_date)}
                      </span>
                      {event.end_date && (
                        <span>→ {formatDate(event.end_date)}</span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

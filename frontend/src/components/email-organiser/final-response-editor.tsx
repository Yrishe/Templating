'use client'

import React, { useState } from 'react'
import { Send, Save, FileText, Plus, Users } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'
import type { FinalResponse, Recipient, PaginatedResponse } from '@/types'

interface FinalResponseEditorProps {
  projectId: string
}

function RecipientList({
  finalResponseId,
}: {
  finalResponseId: string
}) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [showForm, setShowForm] = useState(false)

  const { data } = useQuery({
    queryKey: ['recipients', finalResponseId],
    queryFn: () =>
      api.get<PaginatedResponse<Recipient>>(
        `/api/recipients/?final_response=${finalResponseId}`
      ),
  })

  const addRecipient = useMutation({
    mutationFn: (data: { name: string; email: string; final_response: string }) =>
      api.post<Recipient>('/api/recipients/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recipients', finalResponseId] })
      setName('')
      setEmail('')
      setShowForm(false)
    },
  })

  const recipients = data?.results ?? []

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="flex items-center gap-1.5">
          <Users className="h-3.5 w-3.5" />
          Recipients ({recipients.length})
        </Label>
        <Button variant="ghost" size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <div className="flex gap-2 flex-wrap">
          <Input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 min-w-[120px]"
          />
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1 min-w-[160px]"
          />
          <Button
            size="sm"
            onClick={() =>
              addRecipient.mutate({ name, email, final_response: finalResponseId })
            }
            disabled={!name || !email || addRecipient.isPending}
          >
            Add
          </Button>
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        {recipients.map((r) => (
          <div
            key={r.id}
            className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium"
          >
            <span>{r.name}</span>
            <span className="text-muted-foreground">{'<'}{r.email}{'>'}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

interface ResponseEditorFormProps {
  response: FinalResponse
  onSaved: () => void
}

function ResponseEditorForm({ response, onSaved }: ResponseEditorFormProps) {
  const queryClient = useQueryClient()
  const [subject, setSubject] = useState(response.subject)
  const [content, setContent] = useState(response.content)

  const update = useMutation({
    mutationFn: (data: Partial<FinalResponse>) =>
      api.patch<FinalResponse>(`/api/final-responses/${response.id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['final-responses'] })
      onSaved()
    },
  })

  const send = useMutation({
    mutationFn: () =>
      api.patch<FinalResponse>(`/api/final-responses/${response.id}/`, {
        status: 'sent',
        sent_at: new Date().toISOString(),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['final-responses'] })
    },
  })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="subject">Subject</Label>
        <Input
          id="subject"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="Email subject"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="content">Content</Label>
        <textarea
          id="content"
          className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder="Response content..."
        />
      </div>

      <RecipientList finalResponseId={response.id} />

      <div className="flex gap-2 flex-wrap">
        <Button
          variant="outline"
          size="sm"
          onClick={() => update.mutate({ subject, content })}
          disabled={update.isPending}
        >
          <Save className="h-3.5 w-3.5 mr-1.5" />
          {update.isPending ? 'Saving...' : 'Save Draft'}
        </Button>
        <Button
          size="sm"
          onClick={() => send.mutate()}
          disabled={send.isPending || response.status === 'sent'}
        >
          <Send className="h-3.5 w-3.5 mr-1.5" />
          {send.isPending ? 'Sending...' : response.status === 'sent' ? 'Sent' : 'Send'}
        </Button>
      </div>
    </div>
  )
}

export function FinalResponseEditor({ projectId }: FinalResponseEditorProps) {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['final-responses', projectId],
    queryFn: () =>
      api.get<PaginatedResponse<FinalResponse>>(
        `/api/final-responses/?project=${projectId}`
      ),
  })

  const createResponse = useMutation({
    mutationFn: () =>
      api.post<FinalResponse>('/api/final-responses/', {
        email_organiser: projectId,
        subject: 'New Response',
        content: '',
        status: 'draft',
      }),
    onSuccess: (newResponse) => {
      queryClient.invalidateQueries({ queryKey: ['final-responses', projectId] })
      setEditingId(newResponse.id)
    },
  })

  const responses = data?.results ?? []

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Final Responses
          </CardTitle>
          <Button size="sm" onClick={() => createResponse.mutate()} disabled={createResponse.isPending}>
            <Plus className="h-4 w-4 mr-1" />
            New Response
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="h-24 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        )}

        {!isLoading && responses.length === 0 && (
          <div className="text-center py-8">
            <FileText className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
            <p className="text-sm text-muted-foreground">No responses yet</p>
          </div>
        )}

        <div className="space-y-4">
          {responses.map((response) => (
            <div key={response.id} className="border rounded-md p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm truncate max-w-[200px]">
                    {response.subject || '(No subject)'}
                  </span>
                  <Badge variant={response.status === 'sent' ? 'success' : 'warning'} className="text-[10px]">
                    {response.status}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  {response.sent_at && <span>Sent {formatDateTime(response.sent_at)}</span>}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() =>
                      setEditingId(editingId === response.id ? null : response.id)
                    }
                  >
                    {editingId === response.id ? 'Close' : 'Edit'}
                  </Button>
                </div>
              </div>
              {editingId === response.id && (
                <ResponseEditorForm
                  response={response}
                  onSaved={() => setEditingId(null)}
                />
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

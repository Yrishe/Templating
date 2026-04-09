'use client'

import React, { useEffect, useState } from 'react'
import { Sparkles, RefreshCw, Save, Send, Mail } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { FinalResponse, IncomingEmail } from '@/types'

interface ReplyPanelProps {
  projectId: string
  email: IncomingEmail | null
}

/**
 * ReplyPanel — given a selected inbound email, dynamically generates an
 * AI-drafted reply by calling the backend `generate-reply` endpoint, and
 * lets the user edit + save + send the resulting `FinalResponse`.
 *
 * Generation runs automatically when the selected email changes (and when
 * the user explicitly clicks "Regenerate").
 */
export function ReplyPanel({ projectId, email }: ReplyPanelProps) {
  const [draft, setDraft] = useState<FinalResponse | null>(null)
  const [subject, setSubject] = useState('')
  const [content, setContent] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const generate = useMutation({
    mutationFn: (incomingId: string) =>
      api.post<FinalResponse>(
        `/api/projects/${projectId}/incoming-emails/${incomingId}/generate-reply/`,
        {}
      ),
    onSuccess: (fr) => {
      setDraft(fr)
      setSubject(fr.subject)
      setContent(fr.content)
      setErrorMsg(null)
    },
    onError: (err: Error) => {
      setErrorMsg(err.message || 'Failed to generate reply.')
    },
  })

  // Auto-generate when the selected email changes.
  useEffect(() => {
    setDraft(null)
    setSubject('')
    setContent('')
    setErrorMsg(null)
    if (email) generate.mutate(email.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [email?.id])

  const save = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error('No draft to save.')
      return api.patch<FinalResponse>(
        `/api/email-organiser/${projectId}/final-responses/${draft.id}/`,
        { subject, content }
      )
    },
    onSuccess: (fr) => setDraft(fr),
  })

  const send = useMutation({
    mutationFn: () => {
      if (!draft) throw new Error('No draft to send.')
      return api.post<FinalResponse>(
        `/api/email-organiser/${projectId}/final-responses/${draft.id}/send/`,
        {}
      )
    },
    onSuccess: () => {
      setDraft((d) => (d ? { ...d, status: 'sent' } : d))
    },
  })

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            AI Reply
            {draft?.is_ai_generated && (
              <Badge
                variant="default"
                className="bg-purple-100 text-purple-700 border-purple-200 text-[10px]"
              >
                AI suggested
              </Badge>
            )}
          </CardTitle>
          {email && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => generate.mutate(email.id)}
              disabled={generate.isPending}
              aria-label="Regenerate reply"
            >
              <RefreshCw
                className={`h-4 w-4 mr-1 ${generate.isPending ? 'animate-spin' : ''}`}
              />
              Regenerate
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {!email && (
          <div className="text-center py-12">
            <Mail className="h-10 w-10 text-muted-foreground mx-auto mb-3 opacity-50" />
            <p className="text-sm text-muted-foreground">
              Select an inbound email to generate a reply.
            </p>
          </div>
        )}

        {email && (
          <div className="space-y-4">
            <div className="rounded-md border bg-muted/30 p-3 text-xs space-y-1">
              <div className="font-medium truncate">
                Replying to: {email.subject || '(no subject)'}
              </div>
              <div className="text-muted-foreground truncate">
                From: {email.sender_name || email.sender_email}
              </div>
            </div>

            {generate.isPending && (
              <div className="text-center py-6">
                <Sparkles className="h-6 w-6 text-purple-500 mx-auto animate-pulse mb-2" />
                <p className="text-sm text-muted-foreground">
                  Generating reply from project contract...
                </p>
              </div>
            )}

            {errorMsg && (
              <p className="text-sm text-destructive">{errorMsg}</p>
            )}

            {draft && !generate.isPending && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="reply-subject">Subject</Label>
                  <Input
                    id="reply-subject"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reply-content">Reply</Label>
                  <textarea
                    id="reply-content"
                    className="flex min-h-[240px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                  />
                </div>
                <div className="flex gap-2 flex-wrap">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => save.mutate()}
                    disabled={save.isPending}
                  >
                    <Save className="h-3.5 w-3.5 mr-1.5" />
                    {save.isPending ? 'Saving...' : 'Save Draft'}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => send.mutate()}
                    disabled={send.isPending || draft.status === 'sent'}
                  >
                    <Send className="h-3.5 w-3.5 mr-1.5" />
                    {send.isPending
                      ? 'Sending...'
                      : draft.status === 'sent'
                        ? 'Sent'
                        : 'Send'}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

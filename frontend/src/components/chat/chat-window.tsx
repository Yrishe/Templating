'use client'

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Send, Wifi, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MessageBubble } from './message-bubble'
import { useChat } from '@/hooks/use-chat'
import { useAuth } from '@/hooks/use-auth'
import { api } from '@/lib/api'
import type { Message, PaginatedResponse, User } from '@/types'

interface ChatWindowProps {
  projectId: string
}

// REST returns `author` as a nested User object; the WS broadcast event uses
// `author_id` / `author_email` instead. Normalise to "is this my message?".
function isOwnMessage(msg: Message, currentUserId?: string): boolean {
  if (!currentUserId) return false
  const a = msg.author as unknown
  if (typeof a === 'string') return a === currentUserId
  if (a && typeof a === 'object' && 'id' in a) {
    return (a as { id: string }).id === currentUserId
  }
  const wsAuthorId = (msg as { author_id?: string }).author_id
  return wsAuthorId === currentUserId
}

export function ChatWindow({ projectId }: ChatWindowProps) {
  const { user } = useAuth()
  const [historicalMessages, setHistoricalMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const fetchHistory = useCallback(async () => {
    if (!projectId) return
    try {
      const res = await api.get<PaginatedResponse<Message> | Message[]>(
        `/api/chats/${projectId}/messages/`
      )
      const list = Array.isArray(res) ? res : res.results
      setHistoricalMessages(list ?? [])
    } catch {
      // ignore — chat keeps showing whatever we already have
    }
  }, [projectId])

  // Fetch on mount and poll periodically as a WS-independent fallback so the
  // group chat keeps working when the WebSocket layer is unavailable.
  useEffect(() => {
    fetchHistory()
    const t = setInterval(fetchHistory, 5_000)
    return () => clearInterval(t)
  }, [fetchHistory])

  const { messages: wsMessages, sendMessage, status } = useChat({
    projectId,
    chatId: projectId,
  })

  const allMessages = [...historicalMessages, ...wsMessages]
  const uniqueMessages = allMessages.filter(
    (msg, idx, arr) => arr.findIndex((m) => m.id === msg.id) === idx
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [uniqueMessages.length])

  const handleSend = async () => {
    const content = inputValue.trim()
    if (!content) return
    setInputValue('')

    // Prefer the live WebSocket when it's connected — feels instant. Otherwise
    // fall back to a plain HTTP POST so the chat is never blocked.
    if (status === 'connected') {
      sendMessage(content)
      return
    }

    setSending(true)
    try {
      const created = await api.post<Message>(
        `/api/chats/${projectId}/messages/`,
        { content }
      )
      setHistoricalMessages((prev) => [...prev, created])
    } catch {
      setInputValue(content) // restore so user can retry
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const liveLabel =
    status === 'connected'
      ? { icon: Wifi, klass: 'text-green-500', textKlass: 'text-green-600', label: 'Live' }
      : status === 'connecting'
        ? null
        : {
            icon: WifiOff,
            klass: 'text-muted-foreground',
            textKlass: 'text-muted-foreground',
            label: 'Polling',
          }

  return (
    <div className="flex flex-col h-full min-h-[500px] border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-background">
        <h3 className="font-semibold text-sm">Project Chat</h3>
        <div className="flex items-center gap-1.5 text-xs">
          {status === 'connecting' ? (
            <>
              <div className="h-3.5 w-3.5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="text-muted-foreground">Connecting...</span>
            </>
          ) : liveLabel ? (
            <>
              {React.createElement(liveLabel.icon, {
                className: `h-3.5 w-3.5 ${liveLabel.klass}`,
              })}
              <span className={liveLabel.textKlass}>{liveLabel.label}</span>
            </>
          ) : null}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {uniqueMessages.length === 0 && (
          <div className="text-center py-12">
            <p className="text-sm text-muted-foreground">
              No messages yet. Start the conversation!
            </p>
          </div>
        )}
        {uniqueMessages.map((message) => {
          const author =
            message.author && typeof message.author === 'object'
              ? (message.author as User)
              : undefined
          return (
            <MessageBubble
              key={message.id}
              message={message}
              author={author}
              isOwn={isOwnMessage(message, user?.id)}
            />
          )
        })}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t p-3 bg-background">
        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message..."
            className="flex-1"
            disabled={sending}
          />
          <Button
            onClick={handleSend}
            disabled={!inputValue.trim() || sending}
            size="icon"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

'use client'

import React, { useEffect, useRef, useState } from 'react'
import { Send, Wifi, WifiOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { MessageBubble } from './message-bubble'
import { useChat } from '@/hooks/use-chat'
import { useAuth } from '@/hooks/use-auth'
import { api } from '@/lib/api'
import type { Message, PaginatedResponse, Chat } from '@/types'

interface ChatWindowProps {
  projectId: string
}

export function ChatWindow({ projectId }: ChatWindowProps) {
  const { user } = useAuth()
  const [chatId, setChatId] = useState<string>('')
  const [historicalMessages, setHistoricalMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // Fetch the chat object for this project
  useEffect(() => {
    api
      .get<PaginatedResponse<Chat>>(`/api/chats/?project=${projectId}`)
      .then((res) => {
        if (res.results.length > 0) {
          setChatId(res.results[0].id)
        }
      })
      .catch(() => {})
  }, [projectId])

  // Fetch historical messages
  useEffect(() => {
    if (!chatId) return
    api
      .get<PaginatedResponse<Message>>(`/api/messages/?chat=${chatId}`)
      .then((res) => setHistoricalMessages(res.results))
      .catch(() => {})
  }, [chatId])

  const { messages: wsMessages, sendMessage, status } = useChat({
    projectId,
    chatId,
  })

  const allMessages = [...historicalMessages, ...wsMessages]

  // Remove duplicates (historical messages might overlap with ws messages)
  const uniqueMessages = allMessages.filter(
    (msg, idx, arr) => arr.findIndex((m) => m.id === msg.id) === idx
  )

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [uniqueMessages.length])

  const handleSend = () => {
    const content = inputValue.trim()
    if (!content) return
    sendMessage(content)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full min-h-[500px] border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-background">
        <h3 className="font-semibold text-sm">Project Chat</h3>
        <div className="flex items-center gap-1.5 text-xs">
          {status === 'connected' ? (
            <>
              <Wifi className="h-3.5 w-3.5 text-green-500" />
              <span className="text-green-600">Connected</span>
            </>
          ) : status === 'connecting' ? (
            <>
              <div className="h-3.5 w-3.5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="text-muted-foreground">Connecting...</span>
            </>
          ) : (
            <>
              <WifiOff className="h-3.5 w-3.5 text-destructive" />
              <span className="text-destructive">Disconnected</span>
            </>
          )}
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
        {uniqueMessages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            isOwn={message.author === user?.id}
          />
        ))}
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
            disabled={status !== 'connected'}
          />
          <Button
            onClick={handleSend}
            disabled={!inputValue.trim() || status !== 'connected'}
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

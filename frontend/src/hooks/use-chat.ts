'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { WS_BASE_URL } from '@/lib/constants'
import { accessTokenStore } from '@/lib/api'
import type { Message } from '@/types'

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

interface UseChatOptions {
  projectId: string
  chatId: string
  onMessage?: (message: Message) => void
}

interface UseChatReturn {
  messages: Message[]
  sendMessage: (content: string) => void
  status: ConnectionStatus
  isConnected: boolean
}

export function useChat({ projectId, chatId, onMessage }: UseChatOptions): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([])
  const [status, setStatus] = useState<ConnectionStatus>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const maxReconnectAttempts = 5
  const reconnectAttemptsRef = useRef(0)

  const connect = useCallback(() => {
    if (!projectId || !chatId) return

    // The access token lives in memory only; forward it as a query-string
    // param so the ChatConsumer can parse it on connect and verify via
    // SimpleJWT. The refresh cookie isn't useful here — the WS upgrade
    // doesn't round-trip to /api/auth/ to mint a new access.
    const token = accessTokenStore.get()
    if (!token) {
      setStatus('disconnected')
      return
    }

    setStatus('connecting')
    const wsUrl = `${WS_BASE_URL}/ws/chat/${chatId}/?token=${encodeURIComponent(token)}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('connected')
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as Message
          setMessages((prev) => [...prev, data])
          onMessage?.(data)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        setStatus('disconnected')
        wsRef.current = null

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * 2 ** reconnectAttemptsRef.current, 30_000)
          reconnectAttemptsRef.current += 1
          reconnectTimeoutRef.current = setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        setStatus('error')
      }
    } catch {
      setStatus('error')
    }
  }, [projectId, chatId, onMessage])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ content }))
    }
  }, [])

  return {
    messages,
    sendMessage,
    status,
    isConnected: status === 'connected',
  }
}

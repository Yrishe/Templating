'use client'

import { useParams } from 'next/navigation'
import { ChatWindow } from '@/components/chat/chat-window'

export function ChatPageContent() {
  const { id } = useParams<{ id: string }>()
  return (
    <div className="h-[calc(100vh-16rem)]">
      <ChatWindow projectId={id} />
    </div>
  )
}

import type { Metadata } from 'next'
import { ChatPageContent } from './chat-content'

export const metadata: Metadata = { title: 'Chat' }

export default function ChatPage() {
  return <ChatPageContent />
}

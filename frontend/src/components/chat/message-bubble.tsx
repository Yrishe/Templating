import React from 'react'
import { formatRelativeTime, getInitials } from '@/lib/utils'
import type { Message, User } from '@/types'

interface MessageBubbleProps {
  message: Message
  isOwn: boolean
  author?: User
}

export function MessageBubble({ message, isOwn, author }: MessageBubbleProps) {
  const initials = author
    ? getInitials(author.first_name, author.last_name)
    : message.author.slice(0, 2).toUpperCase()

  const authorName = author
    ? `${author.first_name} ${author.last_name}`
    : 'Unknown User'

  return (
    <div className={`flex gap-2 ${isOwn ? 'flex-row-reverse' : 'flex-row'}`}>
      {!isOwn && (
        <div className="shrink-0 h-7 w-7 rounded-full bg-secondary flex items-center justify-center text-xs font-semibold text-secondary-foreground">
          {initials}
        </div>
      )}
      <div className={`max-w-[70%] ${isOwn ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {!isOwn && (
          <span className="text-xs text-muted-foreground font-medium px-1">{authorName}</span>
        )}
        <div
          className={`rounded-2xl px-4 py-2 text-sm leading-relaxed break-words ${
            isOwn
              ? 'bg-primary text-primary-foreground rounded-tr-none'
              : 'bg-muted text-foreground rounded-tl-none'
          }`}
        >
          {message.content}
        </div>
        <span className="text-[10px] text-muted-foreground px-1">
          {formatRelativeTime(message.created_at)}
        </span>
      </div>
    </div>
  )
}

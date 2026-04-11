'use client'

import React from 'react'
import Link from 'next/link'
import {
  Bell,
  CheckCheck,
  AlertCircle,
  FileText,
  FilePen,
  MessageSquare,
  Info,
  ThumbsUp,
  ThumbsDown,
  Mail,
  Clock,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from '@/hooks/use-notifications'
import { formatRelativeTime } from '@/lib/utils'
import { ROUTES } from '@/lib/constants'
import type { Notification } from '@/types'

// Only project-focused notification types are shown in the dashboard feed.
// `system` and `manager_alert` still appear in the navbar bell dropdown.
const PROJECT_FOCUSED_TYPES: Notification['type'][] = [
  'contract_request',
  'contract_request_approved',
  'contract_request_rejected',
  'contract_update',
  'chat_message',
  'new_email',
  'deadline_upcoming',
]

function NotificationIcon({ type }: { type: Notification['type'] }) {
  switch (type) {
    case 'contract_request':
      return <FileText className="h-4 w-4 text-blue-500" />
    case 'contract_request_approved':
      return <ThumbsUp className="h-4 w-4 text-emerald-500" />
    case 'contract_request_rejected':
      return <ThumbsDown className="h-4 w-4 text-red-500" />
    case 'contract_update':
      return <FilePen className="h-4 w-4 text-purple-500" />
    case 'chat_message':
      return <MessageSquare className="h-4 w-4 text-green-500" />
    case 'new_email':
      return <Mail className="h-4 w-4 text-orange-500" />
    case 'deadline_upcoming':
      return <Clock className="h-4 w-4 text-amber-500" />
    case 'manager_alert':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />
    case 'system':
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

// Notification type → destination page. Clicking a notification deep-links
// the user to the relevant area of the project instead of just marking it
// read. Kept in one place so new types only need one update.
function hrefForNotification(notification: Notification): string {
  switch (notification.type) {
    case 'contract_request':
    case 'contract_request_approved':
    case 'contract_request_rejected':
      return ROUTES.PROJECT_CHANGE_REQUESTS(notification.project)
    case 'contract_update':
      return ROUTES.PROJECT_CONTRACT(notification.project)
    case 'chat_message':
      return ROUTES.PROJECT_CHAT(notification.project)
    case 'new_email':
      return ROUTES.EMAIL_ORGANISER(notification.project)
    case 'deadline_upcoming':
      return ROUTES.PROJECT_TIMELINE(notification.project)
    case 'manager_alert':
    case 'system':
    default:
      return ROUTES.PROJECT(notification.project)
  }
}

function NotificationItem({ notification }: { notification: Notification }) {
  const markRead = useMarkNotificationRead()

  const typeLabels: Record<Notification['type'], string> = {
    contract_request: 'Change Request',
    contract_request_approved: 'Request Approved',
    contract_request_rejected: 'Request Rejected',
    contract_update: 'Contract Update',
    chat_message: 'New Message',
    new_email: 'New Email',
    deadline_upcoming: 'Deadline Upcoming',
    manager_alert: 'Manager Alert',
    system: 'System',
  }

  return (
    <Link
      href={hrefForNotification(notification)}
      onClick={() => markRead.mutate(notification.id)}
      className={`flex gap-3 p-3 rounded-md transition-colors hover:bg-muted cursor-pointer ${
        !notification.is_read ? 'bg-muted/50' : ''
      }`}
    >
      <div className="mt-0.5 shrink-0">
        <NotificationIcon type={notification.type} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-auto">
            {typeLabels[notification.type]}
          </Badge>
          {!notification.is_read && (
            <span className="h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {formatRelativeTime(notification.created_at)}
        </p>
      </div>
    </Link>
  )
}

interface NotificationFeedProps {
  projectId?: string
}

export function NotificationFeed({ projectId }: NotificationFeedProps = {}) {
  const { data, isLoading, isError } = useNotifications(projectId)
  const markAllRead = useMarkAllNotificationsRead()
  const allNotifications = data?.results ?? []
  // Filter to project-focused types only — the dashboard intentionally hides
  // `system` / `manager_alert` to reduce noise. Those still appear in the
  // navbar bell dropdown for users who want the full feed.
  const notifications = allNotifications.filter((n) =>
    PROJECT_FOCUSED_TYPES.includes(n.type)
  )
  const unreadCount = notifications.filter((n) => !n.is_read).length

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Project notifications
            {unreadCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {unreadCount}
              </Badge>
            )}
          </CardTitle>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
              className="text-xs"
            >
              <CheckCheck className="h-3.5 w-3.5 mr-1" />
              Mark all read
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="p-2">
        {isLoading && (
          <div className="flex flex-col gap-2 p-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        )}
        {isError && (
          <p className="text-sm text-destructive text-center py-4">Failed to load notifications</p>
        )}
        {!isLoading && !isError && notifications.length === 0 && (
          <div className="text-center py-8">
            <Bell className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-50" />
            <p className="text-sm text-muted-foreground">No notifications</p>
          </div>
        )}
        {!isLoading && !isError && notifications.length > 0 && (
          <div className="flex flex-col gap-1 max-h-80 overflow-y-auto">
            {notifications.map((notification) => (
              <NotificationItem key={notification.id} notification={notification} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

'use client'

import React from 'react'
import { Bell, Check, CheckCheck, AlertCircle, FileText, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useNotifications, useMarkNotificationRead, useMarkAllNotificationsRead } from '@/hooks/use-notifications'
import { formatRelativeTime } from '@/lib/utils'
import type { Notification } from '@/types'

function NotificationIcon({ type }: { type: Notification['type'] }) {
  switch (type) {
    case 'contract_request':
      return <FileText className="h-4 w-4 text-blue-500" />
    case 'manager_alert':
      return <AlertCircle className="h-4 w-4 text-yellow-500" />
    case 'system':
      return <Info className="h-4 w-4 text-gray-500" />
  }
}

function NotificationItem({ notification }: { notification: Notification }) {
  const markRead = useMarkNotificationRead()

  const typeLabels: Record<Notification['type'], string> = {
    contract_request: 'Contract Request',
    manager_alert: 'Manager Alert',
    system: 'System',
  }

  return (
    <div
      className={`flex gap-3 p-3 rounded-md transition-colors ${
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
      {!notification.is_read && (
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={() => markRead.mutate(notification.id)}
          aria-label="Mark as read"
        >
          <Check className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  )
}

export function NotificationFeed() {
  const { data, isLoading, isError } = useNotifications()
  const markAllRead = useMarkAllNotificationsRead()
  const notifications = data?.results ?? []
  const unreadCount = notifications.filter((n) => !n.is_read).length

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
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

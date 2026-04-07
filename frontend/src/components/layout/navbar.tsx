'use client'

import React from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Bell, LogOut, User, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/hooks/use-auth'
import {
  useNotifications,
  useUnreadNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
} from '@/hooks/use-notifications'
import { MobileSidebar } from '@/components/layout/sidebar'
import { ROUTES } from '@/lib/constants'
import { cn, getInitials, formatRelativeTime } from '@/lib/utils'
import type { Notification } from '@/types'

function getNotificationLabel(type: Notification['type']): string {
  switch (type) {
    case 'contract_request': return 'Contract request'
    case 'contract_update': return 'Contract update'
    case 'chat_message': return 'New message'
    case 'manager_alert': return 'Manager alert'
    default: return 'System notification'
  }
}

function NotificationDropdown() {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const router = useRouter()
  const { data: notifData } = useNotifications()
  const { data: unreadData } = useUnreadNotifications()
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()

  const notifications = (notifData?.results ?? []).slice(0, 8)
  const unreadCount = unreadData?.count ?? 0

  // Close on outside click
  React.useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleMouseEnter = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current)
    setOpen(true)
  }
  const handleMouseLeave = () => {
    closeTimer.current = setTimeout(() => setOpen(false), 300)
  }

  const handleNotificationClick = (n: Notification) => {
    if (!n.is_read) markRead.mutate(n.id)
    router.push(ROUTES.PROJECT(n.project))
    setOpen(false)
  }

  return (
    <div
      ref={ref}
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen((v) => !v)}
        aria-label="Notifications"
        aria-expanded={open}
        className="relative"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold pointer-events-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-80 rounded-lg border bg-background shadow-lg z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <span className="text-sm font-semibold">Notifications</span>
            {unreadCount > 0 && (
              <button
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                onClick={() => markAllRead.mutate()}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">No notifications</p>
            ) : (
              notifications.map((n) => (
                <button
                  key={n.id}
                  onClick={() => handleNotificationClick(n)}
                  className={cn(
                    'w-full text-left flex items-start gap-3 px-4 py-3 hover:bg-accent transition-colors',
                    !n.is_read && 'bg-primary/5'
                  )}
                >
                  <span
                    className={cn(
                      'mt-1.5 h-2 w-2 rounded-full shrink-0',
                      n.is_read ? 'bg-transparent' : 'bg-primary'
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium">{getNotificationLabel(n.type)}</p>
                    <p className="text-xs text-muted-foreground">{formatRelativeTime(n.created_at)}</p>
                  </div>
                </button>
              ))
            )}
          </div>

          {notifications.length > 0 && (
            <div className="border-t px-4 py-2.5">
              <Link
                href={ROUTES.DASHBOARD}
                className="text-xs text-primary hover:underline"
                onClick={() => setOpen(false)}
              >
                View all notifications
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ProfileDropdown() {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)
  const closeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null)
  const { user, logout } = useAuth()
  const router = useRouter()

  // Close on outside click
  React.useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleMouseEnter = () => {
    if (closeTimer.current) clearTimeout(closeTimer.current)
    setOpen(true)
  }
  const handleMouseLeave = () => {
    closeTimer.current = setTimeout(() => setOpen(false), 300)
  }

  const handleLogout = async () => {
    setOpen(false)
    await logout()
    router.push(ROUTES.LOGIN)
  }

  return (
    <div
      ref={ref}
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full p-1 hover:bg-accent transition-colors"
        aria-label="Profile menu"
        aria-expanded={open}
      >
        <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-semibold">
          {getInitials(user?.first_name ?? '', user?.last_name ?? '')}
        </div>
        <div className="hidden md:flex flex-col leading-tight pr-1">
          <span className="text-sm font-medium">
            {user?.first_name} {user?.last_name}
          </span>
          <Badge variant="outline" className="text-[10px] py-0 px-1 capitalize h-auto">
            {user?.role?.replace('_', ' ')}
          </Badge>
        </div>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-52 rounded-lg border bg-background shadow-lg z-50 py-1">
          {/* User info header */}
          <div className="px-4 py-3 border-b mb-1">
            <p className="text-sm font-medium truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
          </div>

          <Link
            href={`/profile/${user?.id}`}
            className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-accent transition-colors"
            onClick={() => setOpen(false)}
          >
            <User className="h-4 w-4 shrink-0" />
            Profile
          </Link>

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-accent transition-colors text-left text-destructive hover:text-destructive"
          >
            <LogOut className="h-4 w-4 shrink-0" />
            Logout
          </button>
        </div>
      )}
    </div>
  )
}

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center gap-4 px-6">
        <MobileSidebar />
        <Link href={ROUTES.DASHBOARD} className="flex items-center gap-2 font-semibold text-lg">
          <FileText className="h-5 w-5 text-primary" />
          <span className="hidden sm:inline">ContractMgr</span>
        </Link>

        <div className="ml-auto flex items-center gap-2">
          <NotificationDropdown />
          <ProfileDropdown />
        </div>
      </div>
    </header>
  )
}

export function UserAvatar({ size = 'sm' }: { size?: 'sm' | 'md' | 'lg' }) {
  const { user } = useAuth()
  if (!user) return null

  const sizeClass = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-10 w-10 text-sm',
    lg: 'h-12 w-12 text-base',
  }[size]

  return (
    <div
      className={`flex rounded-full bg-primary items-center justify-center text-primary-foreground font-semibold ${sizeClass}`}
    >
      {getInitials(user.first_name, user.last_name)}
    </div>
  )
}

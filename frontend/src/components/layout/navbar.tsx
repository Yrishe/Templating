'use client'

import React from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Bell, LogOut, User, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/hooks/use-auth'
import { useUnreadNotifications } from '@/hooks/use-notifications'
import { MobileSidebar } from '@/components/layout/sidebar'
import { ROUTES } from '@/lib/constants'
import { getInitials } from '@/lib/utils'

export function Navbar() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const { data: unreadData } = useUnreadNotifications()
  const unreadCount = unreadData?.count ?? 0

  const handleLogout = async () => {
    await logout()
    router.push(ROUTES.LOGIN)
  }

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center gap-4 px-6">
        <MobileSidebar />
        <Link href={ROUTES.DASHBOARD} className="flex items-center gap-2 font-semibold text-lg">
          <FileText className="h-5 w-5 text-primary" />
          <span className="hidden sm:inline">ContractMgr</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 ml-6 text-sm font-medium">
          <Link
            href={ROUTES.DASHBOARD}
            className="text-foreground/60 hover:text-foreground transition-colors"
          >
            Dashboard
          </Link>
          <Link
            href={ROUTES.PROJECTS}
            className="text-foreground/60 hover:text-foreground transition-colors"
          >
            Projects
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <Link href={ROUTES.DASHBOARD} className="relative">
            <Button variant="ghost" size="icon" aria-label="Notifications">
              <Bell className="h-5 w-5" />
            </Button>
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Link>

          <div className="flex items-center gap-2">
            <div className="hidden sm:flex h-8 w-8 rounded-full bg-primary items-center justify-center text-primary-foreground text-xs font-semibold">
              {getInitials(user?.first_name ?? '', user?.last_name ?? '')}
            </div>
            <div className="hidden md:flex flex-col leading-tight">
              <span className="text-sm font-medium">
                {user?.first_name} {user?.last_name}
              </span>
              <Badge variant="outline" className="text-[10px] py-0 px-1 capitalize h-auto">
                {user?.role?.replace('_', ' ')}
              </Badge>
            </div>
          </div>

          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Logout">
            <LogOut className="h-4 w-4" />
          </Button>
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

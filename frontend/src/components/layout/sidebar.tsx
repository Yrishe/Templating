'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FolderOpen,
  Mail,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES } from '@/lib/constants'

interface NavItem {
  label: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  roles?: string[]
}

const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    href: ROUTES.DASHBOARD,
    icon: LayoutDashboard,
  },
  {
    label: 'Projects',
    href: ROUTES.PROJECTS,
    icon: FolderOpen,
  },
  {
    label: 'Email Organiser',
    href: '/email-organiser',
    icon: Mail,
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: Settings,
  },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = React.useState(false)
  const pathname = usePathname()
  const { user } = useAuth()

  const filteredItems = navItems.filter((item) => {
    if (!item.roles) return true
    if (!user) return false
    return item.roles.includes(user.role)
  })

  return (
    <aside
      className={cn(
        'hidden lg:flex flex-col border-r border-white/60 bg-white/60 backdrop-blur-md min-h-[calc(100vh-3.5rem)] transition-all duration-200 overflow-hidden dark:border-white/10 dark:bg-slate-900/50',
        collapsed ? 'w-16' : 'w-64'
      )}
    >
      {/* Collapse toggle */}
      <div className={cn('flex p-2 pt-3', collapsed ? 'justify-center' : 'justify-end')}>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="p-1.5 rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>

      <nav className="flex flex-col gap-1 px-2 pb-4">
        {filteredItems.map((item) => {
          const Icon = item.icon
          const isActive =
            pathname === item.href ||
            (item.href !== ROUTES.DASHBOARD && pathname.startsWith(item.href))

          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed ? item.label : undefined}
              aria-label={collapsed ? item.label : undefined}
              className={cn(
                'flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
                collapsed ? 'justify-center gap-0 px-2' : 'gap-3',
                isActive
                  ? 'bg-gradient-to-r from-primary to-primary/85 text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-white/70 hover:text-foreground dark:hover:bg-white/5'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="flex-1">{item.label}</span>}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}

export function MobileSidebar() {
  const [isOpen, setIsOpen] = React.useState(false)
  const pathname = usePathname()
  const { user } = useAuth()

  React.useEffect(() => {
    setIsOpen(false)
  }, [pathname])

  const filteredItems = navItems.filter((item) => {
    if (!item.roles) return true
    if (!user) return false
    return item.roles.includes(user.role)
  })

  return (
    <div className="lg:hidden">
      <button
        className="p-2 rounded-md hover:bg-accent"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Toggle navigation"
      >
        <div className="space-y-1">
          <span className="block w-5 h-0.5 bg-foreground"></span>
          <span className="block w-5 h-0.5 bg-foreground"></span>
          <span className="block w-5 h-0.5 bg-foreground"></span>
        </div>
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50" onClick={() => setIsOpen(false)}>
          <div
            className="absolute left-0 top-0 h-full w-64 bg-background border-r shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <nav className="flex flex-col gap-1 p-4 pt-14">
              {filteredItems.map((item) => {
                const Icon = item.icon
                const isActive =
                  pathname === item.href ||
                  (item.href !== ROUTES.DASHBOARD && pathname.startsWith(item.href))

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      )}
    </div>
  )
}

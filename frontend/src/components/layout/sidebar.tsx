'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FolderOpen,
  PlusCircle,
  Mail,
  Settings,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES, USER_ROLES } from '@/lib/constants'

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
    label: 'New Project',
    href: ROUTES.NEW_PROJECT,
    icon: PlusCircle,
    roles: [USER_ROLES.MANAGER, USER_ROLES.SUBSCRIBER],
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
  const pathname = usePathname()
  const { user } = useAuth()

  const filteredItems = navItems.filter((item) => {
    if (!item.roles) return true
    if (!user) return false
    return item.roles.includes(user.role)
  })

  return (
    <aside className="hidden lg:flex w-64 flex-col border-r bg-background min-h-[calc(100vh-3.5rem)]">
      <nav className="flex flex-col gap-1 p-4">
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
              <span className="flex-1">{item.label}</span>
              {isActive && <ChevronRight className="h-4 w-4" />}
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

  // Close on route change
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

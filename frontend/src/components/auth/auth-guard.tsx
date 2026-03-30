'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/hooks/use-auth'
import { ROUTES } from '@/lib/constants'

interface AuthGuardProps {
  children: React.ReactNode
  requiredRoles?: string[]
}

export function AuthGuard({ children, requiredRoles }: AuthGuardProps) {
  const { user, isLoading, isAuthenticated } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (isLoading) return

    if (!isAuthenticated) {
      router.replace(ROUTES.LOGIN)
      return
    }

    if (requiredRoles && user && !requiredRoles.includes(user.role)) {
      router.replace(ROUTES.DASHBOARD)
    }
  }, [isLoading, isAuthenticated, user, router, requiredRoles])

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  if (requiredRoles && user && !requiredRoles.includes(user.role)) {
    return null
  }

  return <>{children}</>
}

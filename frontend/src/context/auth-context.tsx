'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, tokenStorage } from '@/lib/api'
import type { User, LoginCredentials, SignupData } from '@/types'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => Promise<void>
  signup: (data: SignupData) => Promise<void>
  refreshUser: () => Promise<void>
}

interface AuthResponseBody {
  user: User
  access: string
  refresh: string
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    // If this tab has no access token in sessionStorage there's nothing to
    // check — skip the /me call to avoid a guaranteed 401 on a fresh tab.
    if (!tokenStorage.getAccess()) {
      setUser(null)
      return
    }
    try {
      const me = await api.get<User>('/api/auth/me/')
      setUser(me)
    } catch {
      setUser(null)
      tokenStorage.clear()
    }
  }, [])

  useEffect(() => {
    refreshUser().finally(() => setIsLoading(false))
  }, [refreshUser])

  const login = useCallback(async (credentials: LoginCredentials) => {
    const resp = await api.post<AuthResponseBody>('/api/auth/login/', credentials)
    tokenStorage.set(resp.access, resp.refresh)
    setUser(resp.user)
  }, [])

  const logout = useCallback(async () => {
    const refresh = tokenStorage.getRefresh()
    try {
      await api.post('/api/auth/logout/', { refresh })
    } finally {
      // Always clear local state — a network failure on blacklist shouldn't
      // trap the user in a "logged in" UI for this tab.
      tokenStorage.clear()
      setUser(null)
    }
  }, [])

  const signup = useCallback(async (data: SignupData) => {
    const resp = await api.post<AuthResponseBody>('/api/auth/signup/', data)
    tokenStorage.set(resp.access, resp.refresh)
    setUser(resp.user)
  }, [])

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: user !== null,
    login,
    logout,
    signup,
    refreshUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}

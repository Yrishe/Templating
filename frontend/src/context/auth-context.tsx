'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { accessTokenStore, api, tryRefreshToken } from '@/lib/api'
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
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!accessTokenStore.get()) {
      setUser(null)
      return
    }
    try {
      const me = await api.get<User>('/api/auth/me/')
      setUser(me)
    } catch {
      setUser(null)
      accessTokenStore.clear()
    }
  }, [])

  useEffect(() => {
    // Every page load starts with no access token in memory. Ask the
    // refresh endpoint whether the browser still has a valid HttpOnly
    // refresh cookie; if yes, mint a fresh access and hydrate /me.
    void (async () => {
      const ok = await tryRefreshToken()
      if (ok) {
        try {
          const me = await api.get<User>('/api/auth/me/')
          setUser(me)
        } catch {
          setUser(null)
        }
      } else {
        setUser(null)
      }
      setIsLoading(false)
    })()
  }, [])

  const login = useCallback(async (credentials: LoginCredentials) => {
    const resp = await api.post<AuthResponseBody>('/api/auth/login/', credentials)
    accessTokenStore.set(resp.access)
    setUser(resp.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout/', {})
    } finally {
      // Always clear local state — a network failure on blacklist shouldn't
      // trap the user in a "logged in" UI. The server also clears the
      // HttpOnly cookie on its response; we only own the in-memory access.
      accessTokenStore.clear()
      setUser(null)
    }
  }, [])

  const signup = useCallback(async (data: SignupData) => {
    const resp = await api.post<AuthResponseBody>('/api/auth/signup/', data)
    accessTokenStore.set(resp.access)
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

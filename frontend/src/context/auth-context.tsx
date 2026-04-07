'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from '@/lib/api'
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

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.get<User>('/api/auth/me/')
      setUser(me)
    } catch {
      setUser(null)
    }
  }, [])

  useEffect(() => {
    refreshUser().finally(() => setIsLoading(false))
  }, [refreshUser])

  const login = useCallback(async (credentials: LoginCredentials) => {
    const user = await api.post<User>('/api/auth/login/', credentials)
    setUser(user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout/', {})
    } finally {
      setUser(null)
    }
  }, [])

  const signup = useCallback(async (data: SignupData) => {
    const user = await api.post<User>('/api/auth/signup/', data)
    setUser(user)
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

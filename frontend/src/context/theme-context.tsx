'use client'

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'

// Theme controls the base surface/background palette. `system` follows the
// user's OS setting and keeps reacting to changes via `matchMedia`.
export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'ui.theme'

interface ThemeContextValue {
  preference: ThemePreference
  resolved: ResolvedTheme
  setPreference: (value: ThemePreference) => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

// Reads the OS-level preference. Safe for SSR — returns 'light' on the server
// because `window` is undefined there; the effect below corrects it on mount.
function getSystemTheme(): ResolvedTheme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function resolveTheme(pref: ThemePreference): ResolvedTheme {
  return pref === 'system' ? getSystemTheme() : pref
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Default to 'system' on first render to avoid a hydration mismatch (the
  // server always produces light markup). The effect below reads
  // localStorage on mount and rewires if the user picked something else.
  const [preference, setPreferenceState] = useState<ThemePreference>('system')
  const [resolved, setResolved] = useState<ResolvedTheme>('light')

  // Hydrate from localStorage on mount.
  useEffect(() => {
    const stored =
      typeof window !== 'undefined'
        ? (window.localStorage.getItem(STORAGE_KEY) as ThemePreference | null)
        : null
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      setPreferenceState(stored)
    }
  }, [])

  // Apply the resolved theme to <html> and keep it in sync with OS changes
  // when the preference is "system".
  useEffect(() => {
    const apply = () => {
      const next = resolveTheme(preference)
      setResolved(next)
      const root = document.documentElement
      root.classList.toggle('dark', next === 'dark')
    }
    apply()
    if (preference !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => apply()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [preference])

  const setPreference = useCallback((value: ThemePreference) => {
    setPreferenceState(value)
    try {
      window.localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // localStorage can throw in privacy modes — best-effort persistence.
    }
  }, [])

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within a ThemeProvider')
  return ctx
}

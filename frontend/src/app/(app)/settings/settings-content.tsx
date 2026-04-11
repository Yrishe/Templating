'use client'

import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { useTheme, type ThemePreference } from '@/context/theme-context'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { User } from '@/types'

// Three-way theme toggle: light / dark / system. `system` follows the OS
// setting and keeps reacting to changes via a matchMedia listener in the
// ThemeProvider.
const THEME_OPTIONS: { value: ThemePreference; label: string; Icon: typeof Sun; hint: string }[] = [
  { value: 'light', label: 'Light', Icon: Sun, hint: 'Always use the light palette' },
  { value: 'dark', label: 'Dark', Icon: Moon, hint: 'Always use the dark palette' },
  { value: 'system', label: 'System', Icon: Monitor, hint: 'Follow your OS preference' },
]

function ThemeSelector() {
  const { preference, setPreference } = useTheme()
  return (
    <div className="grid grid-cols-3 gap-3">
      {THEME_OPTIONS.map(({ value, label, Icon, hint }) => {
        const isActive = preference === value
        return (
          <button
            key={value}
            type="button"
            onClick={() => setPreference(value)}
            aria-pressed={isActive}
            className={cn(
              'flex flex-col items-center gap-2 rounded-xl border p-4 text-sm transition-all duration-150',
              isActive
                ? 'border-primary bg-primary/10 text-foreground [box-shadow:var(--shadow-soft)]'
                : 'border-border bg-white/60 text-muted-foreground hover:border-border hover:bg-white/80 dark:bg-slate-900/40 dark:hover:bg-slate-900/60'
            )}
          >
            <Icon className={cn('h-5 w-5', isActive && 'text-primary')} />
            <span className="font-medium">{label}</span>
            <span className="text-[11px] text-muted-foreground text-center leading-tight">
              {hint}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function SettingsContent() {
  const { user, refreshUser } = useAuth()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)

  useEffect(() => {
    if (user) {
      setFirstName(user.first_name)
      setLastName(user.last_name)
    }
  }, [user])

  if (!user) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!firstName.trim() || !lastName.trim()) return
    setIsSaving(true)
    setSaveError(null)
    setSaveSuccess(false)
    try {
      await api.patch<User>('/api/auth/me/', { first_name: firstName, last_name: lastName })
      await refreshUser()
      setSaveSuccess(true)
    } catch {
      setSaveError('Failed to save changes. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account details.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>
            Choose how ContractMgr looks. Your preference is saved in this browser only.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ThemeSelector />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Update your name. Email and role cannot be changed here.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">First name</Label>
                <Input
                  id="first_name"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last name</Label>
                <Input
                  id="last_name"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Email</Label>
              <Input value={user.email} readOnly className="bg-muted" />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <div>
                <Badge variant="outline" className="capitalize">
                  {user.role?.replace('_', ' ') ?? 'Unknown'}
                </Badge>
              </div>
            </div>
            {saveError && <p className="text-sm text-destructive">{saveError}</p>}
            {saveSuccess && <p className="text-sm text-green-600">Changes saved.</p>}
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save changes'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

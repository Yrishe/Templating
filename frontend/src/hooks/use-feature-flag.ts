import { useAuth } from '@/context/auth-context'
import type { FeatureFlags } from '@/types'

// ─── Phase 1 feature flags ───────────────────────────────────────────────
//
// Tiny env-driven gates so a feature can be dark-launched and pulled
// without a redeploy. The backend exposes them via /api/auth/me/ (see
// accounts/serializers.py UserProfileSerializer.features); this hook
// reads that block from the auth context.
//
// For SSR / pre-auth boots we also honour a build-time NEXT_PUBLIC_
// fallback so the widget can render in Storybook or anonymous preview
// paths without a server call.

const ENV_FALLBACKS: Record<keyof FeatureFlags, boolean> = {
  ai_thumbs: (process.env.NEXT_PUBLIC_FEATURE_AI_THUMBS ?? 'false').toLowerCase() === 'true',
}

export function useFeatureFlag(flag: keyof FeatureFlags): boolean {
  const { user } = useAuth()
  const serverValue = user?.features?.[flag]
  if (typeof serverValue === 'boolean') return serverValue
  return ENV_FALLBACKS[flag] ?? false
}

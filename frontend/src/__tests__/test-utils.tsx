import React from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * Creates a fresh QueryClient for each test — disables retries so failures
 * surface immediately and gcTime=0 prevents stale cache between tests.
 */
export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

function QueryWrapper({ children }: { children: React.ReactNode }) {
  const queryClient = makeQueryClient()
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

/** Render with only React Query — use for components that don't depend on useAuth. */
export function renderWithQuery(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: QueryWrapper, ...options })
}

/** Mock user object matching the MSW handler fixtures in src/mocks/handlers.ts */
export const mockUser = {
  id: 'user-1',
  email: 'account@example.com',
  first_name: 'Alice',
  last_name: 'Account',
  role: 'account' as const,
  is_active: true,
}

export * from '@testing-library/react'

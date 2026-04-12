import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { IncomingEmail, PaginatedResponse } from '@/types'

export const emailKeys = {
  all: ['incoming-emails'] as const,
  list: (projectId: string) => [...emailKeys.all, projectId] as const,
  detail: (projectId: string, emailId: string) =>
    [...emailKeys.all, projectId, emailId] as const,
}

interface ListParams {
  projectId: string
  category?: string
  relevance?: string
  is_resolved?: string
  is_relevant?: string
}

export function useIncomingEmails({
  projectId,
  category,
  relevance,
  is_resolved,
  is_relevant,
}: ListParams) {
  return useQuery({
    queryKey: [...emailKeys.list(projectId), { category, relevance, is_resolved, is_relevant }],
    queryFn: () => {
      const params = new URLSearchParams()
      if (category) params.set('category', category)
      if (relevance) params.set('relevance', relevance)
      if (is_resolved !== undefined) params.set('is_resolved', is_resolved)
      if (is_relevant !== undefined) params.set('is_relevant', is_relevant)
      const qs = params.toString()
      return api.get<PaginatedResponse<IncomingEmail>>(
        `/api/projects/${projectId}/incoming-emails/${qs ? `?${qs}` : ''}`
      )
    },
    refetchInterval: 30_000,
    enabled: Boolean(projectId),
  })
}

export function useIncomingEmail(projectId: string, emailId: string) {
  return useQuery({
    queryKey: emailKeys.detail(projectId, emailId),
    queryFn: () =>
      api.get<IncomingEmail>(
        `/api/projects/${projectId}/incoming-emails/${emailId}/`
      ),
    enabled: Boolean(projectId && emailId),
  })
}

export function useResolveEmail(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) =>
      api.post<IncomingEmail>(
        `/api/projects/${projectId}/incoming-emails/${emailId}/resolve/`,
        {}
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailKeys.list(projectId) })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useReanalyseEmail(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (emailId: string) =>
      api.post(
        `/api/projects/${projectId}/incoming-emails/${emailId}/reanalyse/`,
        {}
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailKeys.list(projectId) })
    },
  })
}

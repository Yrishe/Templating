import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  Project,
  PaginatedResponse,
  Contract,
  ContractRequest,
  ProjectMembership,
  Timeline,
  TimelineEvent,
  Tag,
} from '@/types'

export const projectKeys = {
  all: ['projects'] as const,
  lists: () => [...projectKeys.all, 'list'] as const,
  list: (filters?: Record<string, string>) => [...projectKeys.lists(), filters] as const,
  details: () => [...projectKeys.all, 'detail'] as const,
  detail: (id: string) => [...projectKeys.details(), id] as const,
  contracts: (projectId: string) => [...projectKeys.detail(projectId), 'contracts'] as const,
  contract: (projectId: string) => [...projectKeys.contracts(projectId)] as const,
  contractRequests: (projectId: string) =>
    [...projectKeys.detail(projectId), 'contract-requests'] as const,
  members: (projectId: string) => [...projectKeys.detail(projectId), 'members'] as const,
  timeline: (projectId: string) => [...projectKeys.detail(projectId), 'timeline'] as const,
}

export function useProjects() {
  return useQuery({
    queryKey: projectKeys.lists(),
    queryFn: () => api.get<PaginatedResponse<Project>>('/api/projects/'),
  })
}

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => api.get<Project>(`/api/projects/${id}/`),
    enabled: Boolean(id),
  })
}

// Project create accepts an optional `tag_ids` array of Tag UUIDs to attach.
type CreateProjectPayload = Partial<Project> & { tag_ids?: string[] }

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateProjectPayload) =>
      api.post<Project>('/api/projects/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
    },
  })
}

// ─── Tags ────────────────────────────────────────────────────────────────
export const tagKeys = {
  all: ['tags'] as const,
  list: () => [...tagKeys.all, 'list'] as const,
}

export function useTags() {
  return useQuery({
    queryKey: tagKeys.list(),
    queryFn: () => api.get<Tag[]>('/api/tags/'),
  })
}

export function useCreateTag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { name: string; color: string }) =>
      api.post<Tag>('/api/tags/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: tagKeys.list() })
    },
  })
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Project>) => api.patch<Project>(`/api/projects/${id}/`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(id) })
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/projects/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
    },
  })
}

export function useProjectContract(projectId: string) {
  return useQuery({
    queryKey: projectKeys.contract(projectId),
    queryFn: () => api.get<PaginatedResponse<Contract>>(`/api/contracts/?project=${projectId}`),
    enabled: Boolean(projectId),
  })
}

export function useCreateContract() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: FormData | Partial<Contract>) => {
      if (data instanceof FormData) {
        return api.postForm<Contract>('/api/contracts/', data)
      }
      return api.post<Contract>('/api/contracts/', data)
    },
    onSuccess: (contract) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contract(contract.project) })
    },
  })
}

export function useUpdateContract(contractId: string, projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: FormData | Partial<Contract>) => {
      if (data instanceof FormData) {
        return api.patchForm<Contract>(`/api/contracts/${contractId}/`, data)
      }
      return api.patch<Contract>(`/api/contracts/${contractId}/`, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contract(projectId) })
    },
  })
}

export function useActivateContract(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (contractId: string) =>
      api.post<Contract>(`/api/contracts/${contractId}/activate/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contract(projectId) })
    },
  })
}

export function useContractRequests(projectId?: string) {
  return useQuery({
    queryKey: projectId ? projectKeys.contractRequests(projectId) : ['contract-requests'],
    queryFn: () => {
      const url = projectId
        ? `/api/contract-requests/?project=${projectId}`
        : '/api/contract-requests/'
      return api.get<PaginatedResponse<ContractRequest>>(url)
    },
  })
}

export function useCreateContractRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<ContractRequest>) =>
      api.post<ContractRequest>('/api/contract-requests/', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-requests'] })
    },
  })
}

export function useApproveContractRequest(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post<ContractRequest>(`/api/contract-requests/${id}/approve/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contractRequests(projectId) })
      queryClient.invalidateQueries({ queryKey: projectKeys.contract(projectId) })
    },
  })
}

export function useRejectContractRequest(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post<ContractRequest>(`/api/contract-requests/${id}/reject/`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.contractRequests(projectId) })
    },
  })
}

export function useProjectMembers(projectId: string) {
  return useQuery({
    queryKey: projectKeys.members(projectId),
    queryFn: () =>
      api.get<PaginatedResponse<ProjectMembership>>(
        `/api/project-memberships/?project=${projectId}`
      ),
    enabled: Boolean(projectId),
  })
}

export function useProjectTimeline(projectId: string) {
  return useQuery({
    queryKey: projectKeys.timeline(projectId),
    queryFn: () => api.get<Timeline>(`/api/projects/${projectId}/timeline/`),
    enabled: Boolean(projectId),
  })
}

export function useCreateTimelineEvent() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ projectId, ...data }: Partial<TimelineEvent> & { projectId: string }) =>
      api.post<TimelineEvent>(`/api/projects/${projectId}/timeline/events/`, data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.timeline(variables.projectId) })
    },
  })
}

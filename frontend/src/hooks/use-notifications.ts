import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Notification, PaginatedResponse, DashboardData } from '@/types'

export const notificationKeys = {
  all: ['notifications'] as const,
  lists: () => [...notificationKeys.all, 'list'] as const,
  unread: () => [...notificationKeys.all, 'unread'] as const,
  dashboard: ['dashboard'] as const,
}

export function useNotifications() {
  return useQuery({
    queryKey: notificationKeys.lists(),
    queryFn: () => api.get<PaginatedResponse<Notification>>('/api/notifications/'),
    refetchInterval: 30_000, // poll every 30s
  })
}

export function useUnreadNotifications() {
  return useQuery({
    queryKey: notificationKeys.unread(),
    queryFn: () => api.get<PaginatedResponse<Notification>>('/api/notifications/?is_read=false'),
    refetchInterval: 15_000,
  })
}

export function useMarkNotificationRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.patch<Notification>(`/api/notifications/${id}/`, { is_read: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

export function useMarkAllNotificationsRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post('/api/notifications/mark-all-read/', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all })
    },
  })
}

export function useDashboard() {
  return useQuery({
    queryKey: notificationKeys.dashboard,
    queryFn: () => api.get<DashboardData>('/api/dashboard/'),
    refetchInterval: 30_000,
  })
}

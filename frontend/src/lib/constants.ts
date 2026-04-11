export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const USER_ROLES = {
  MANAGER: 'manager',
  ACCOUNT: 'account',
  SUBSCRIBER: 'account',  // backward-compat alias
  INVITED_ACCOUNT: 'invited_account',
} as const

export const CONTRACT_STATUS = {
  DRAFT: 'draft',
  ACTIVE: 'active',
  EXPIRED: 'expired',
} as const

export const CONTRACT_REQUEST_STATUS = {
  PENDING: 'pending',
  APPROVED: 'approved',
  REJECTED: 'rejected',
} as const

export const NOTIFICATION_TYPE = {
  CONTRACT_REQUEST: 'contract_request',
  MANAGER_ALERT: 'manager_alert',
  SYSTEM: 'system',
} as const

export const TIMELINE_EVENT_STATUS = {
  PLANNED: 'planned',
  IN_PROGRESS: 'in_progress',
  COMPLETED: 'completed',
} as const

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  SIGNUP: '/signup',
  DASHBOARD: '/dashboard',
  PROJECTS: '/projects',
  NEW_PROJECT: '/projects/new',
  PROJECT: (id: string) => `/projects/${id}`,
  PROJECT_CHAT: (id: string) => `/projects/${id}/chat`,
  PROJECT_CONTRACT: (id: string) => `/projects/${id}/contract`,
  PROJECT_CHANGE_REQUESTS: (id: string) => `/projects/${id}/change-requests`,
  PROJECT_TIMELINE: (id: string) => `/projects/${id}/timeline`,
  PROJECT_INVITE: (id: string) => `/projects/${id}/invite`,
  EMAIL_ORGANISER: (projectId: string) => `/email-organiser/${projectId}`,
} as const

export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8000'

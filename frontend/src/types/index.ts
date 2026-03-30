export type UserRole = 'manager' | 'subscriber' | 'invited_account'

export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
}

export interface Account {
  id: string
  subscriber: string // User ID
  name: string
  email: string
  created_at: string
  updated_at: string
}

export interface Project {
  id: string
  account: string
  name: string
  description: string
  generic_email: string
  created_at: string
  updated_at: string
}

export interface ProjectMembership {
  project: string
  user: string
  joined_at: string
}

export type ContractStatus = 'draft' | 'active' | 'expired'
export interface Contract {
  id: string
  project: string
  title: string
  content: string
  status: ContractStatus
  created_by: string
  created_at: string
  updated_at: string
  activated_at: string | null
}

export type ContractRequestStatus = 'pending' | 'approved' | 'rejected'
export interface ContractRequest {
  id: string
  account: string
  project: string
  description: string
  status: ContractRequestStatus
  created_at: string
  reviewed_at: string | null
  reviewed_by: string | null
}

export type NotificationType = 'contract_request' | 'manager_alert' | 'system'
export interface Notification {
  id: string
  project: string
  type: NotificationType
  is_read: boolean
  triggered_by_contract_request: string | null
  triggered_by_manager: string | null
  created_at: string
}

export interface Message {
  id: string
  chat: string
  author: string
  content: string
  created_at: string
  updated_at: string
}

export interface TimelineEvent {
  id: string
  timeline: string
  title: string
  description: string
  start_date: string
  end_date: string | null
  status: 'planned' | 'in_progress' | 'completed'
  created_at: string
}

export interface InvitedAccount {
  id: string
  project: string
  user: string
  invited_at: string
}

export type FinalResponseStatus = 'draft' | 'sent'
export interface FinalResponse {
  id: string
  email_organiser: string
  edited_by: string | null
  subject: string
  content: string
  status: FinalResponseStatus
  created_at: string
  sent_at: string | null
}

export interface Recipient {
  id: string
  name: string
  email: string
  final_response: string
}

export interface DashboardData {
  user: User
  notifications: Notification[]
  projects: Project[]
  recent_contract_requests: ContractRequest[]
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface SignupData {
  email: string
  password: string
  first_name: string
  last_name: string
  role: UserRole
}

export interface AuthResponse {
  user: User
  access: string
  refresh: string
}

export interface Chat {
  id: string
  project: string
  created_at: string
}

export interface EmailOrganiser {
  id: string
  project: string
  created_at: string
  updated_at: string
}

export interface Timeline {
  id: string
  project: string
  created_at: string
}

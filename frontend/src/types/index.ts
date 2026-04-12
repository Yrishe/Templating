export type UserRole = 'manager' | 'account' | 'invited_account'

export interface User {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  is_active: boolean
}

export interface Account {
  id: string
  subscriber: string // User ID
  name: string
  email: string
  created_at: string
  updated_at: string
}

export type ProjectStatus = 'active' | 'completed' | 'archived'

export interface Tag {
  id: string
  name: string
  color: string
  created_at: string
}

export interface Project {
  id: string
  account: string
  /** User ID of the Account's subscriber (i.e. the project's real owner). */
  account_subscriber_id: string | null
  name: string
  description: string
  generic_email: string
  status: ProjectStatus
  tags: Tag[]
  created_at: string
  updated_at: string
}

export interface ProjectMembership {
  project: string
  user: string
  joined_at: string
}

export type ContractStatus = 'draft' | 'active' | 'expired'
export type ContractTextSource = 'none' | 'pypdf' | 'textract' | 'manual'
export interface Contract {
  id: string
  project: string
  title: string
  file: string | null
  file_url: string | null
  content: string
  text_source: ContractTextSource
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
  attachment: string | null
  attachment_url: string | null
  status: ContractRequestStatus
  review_comment: string
  created_at: string
  reviewed_at: string | null
  reviewed_by: string | null
}

export type NotificationType =
  | 'contract_request'
  | 'contract_request_approved'
  | 'contract_request_rejected'
  | 'contract_update'
  | 'chat_message'
  | 'new_email'
  | 'deadline_upcoming'
  | 'timeline_comment'
  | 'email_high_relevance'
  | 'email_occurrence_unresolved'
  | 'manager_alert'
  | 'system'
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

export type TimelineEventPriority = 'low' | 'medium' | 'high' | 'critical'
export type TimelineCommentType =
  | 'general'
  | 'completion_confirmation'
  | 'status_update'
  | 'feedback'
  | 'suggestion'

export interface TimelineComment {
  id: string
  event: string
  author: User
  content: string
  comment_type: TimelineCommentType
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
  priority: TimelineEventPriority
  created_by: User | null
  deadline_reminder_days: number
  comments: TimelineComment[]
  comment_count: number
  created_at: string
  updated_at: string
}

export interface Timeline {
  id: string
  project: string
  events: TimelineEvent[]
  created_at: string
  updated_at: string
}

export interface InvitedAccount {
  id: string
  project: string
  user: string
  invited_at: string
}

export type FinalResponseStatus = 'draft' | 'suggested' | 'sent'
export interface FinalResponse {
  id: string
  email_organiser: string
  edited_by: string | null
  source_incoming_email: string | null
  subject: string
  content: string
  status: FinalResponseStatus
  is_ai_generated: boolean
  created_at: string
  sent_at: string | null
}

export type EmailRelevance = 'high' | 'medium' | 'low' | 'none'
export type EmailCategory =
  | 'delay'
  | 'damage'
  | 'scope_change'
  | 'costs'
  | 'delivery'
  | 'compliance'
  | 'quality'
  | 'dispute'
  | 'general'
  | 'irrelevant'

export interface EmailAnalysis {
  id: string
  email: string
  agent_topic: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_summary: string
  contract_references: string
  mitigation: string
  suggested_response: string
  resolution_path: string
  timeline_impact: string
  generated_timeline_event: string | null
  created_at: string
}

export interface IncomingEmail {
  id: string
  project: string
  sender_email: string
  sender_name: string
  subject: string
  body_plain: string
  body_html: string
  message_id: string
  received_at: string
  is_processed: boolean
  is_relevant: boolean
  relevance: EmailRelevance
  category: EmailCategory
  keywords: string
  is_resolved: boolean
  analysis: EmailAnalysis | null
  created_at: string
}

export interface Recipient {
  id: string
  name: string
  email: string
  final_response: string
}

export interface DashboardData {
  role: string
  unread_notification_count: number
  project_count: number
  completed_projects: number
  recent_notifications: Notification[]
  recent_projects: Project[]
  pending_contract_requests: number
  active_contracts: number
  account_count: number
  pending_manager_count: number
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
  role: 'account' | 'manager'
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

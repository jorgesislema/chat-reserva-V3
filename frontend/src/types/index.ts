export interface Tenant {
  id: string
  slug: string
  name: string
  legal_name: string | null
  status: 'active' | 'paused' | 'deleted'
  timezone: string
  locale: string
  currency: string
  business_type: string | null
  labels_json: Record<string, string>
  settings_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Resource {
  id: string
  tenant_id: string
  name: string
  kind: string
  email: string | null
  phone: string | null
  active: boolean
  sort_order: number
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Service {
  id: string
  tenant_id: string
  name: string
  description: string
  category: string | null
  duration_min: number
  buffer_before_min: number
  buffer_after_min: number
  price_cents: number
  currency: string
  active: boolean
  sort_order: number
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Schedule {
  id: string
  tenant_id: string
  resource_id: string
  weekday: number
  start_time: string
  end_time: string
  valid_from: string | null
  valid_to: string | null
  created_at: string
  updated_at: string
}

export interface ScheduleException {
  id: string
  tenant_id: string
  resource_id: string
  exception_date: string
  exception_type: 'closed' | 'extra' | 'modified'
  start_time: string | null
  end_time: string | null
  reason: string
  created_at: string
  updated_at: string
}

export interface FAQ {
  id: string
  tenant_id: string
  question: string
  answer: string
  category: string | null
  priority: number
  active: boolean
  created_at: string
  updated_at: string
}

export interface Policy {
  id: string
  tenant_id: string
  key: string
  title: string
  body: string
  category: string | null
  version: number
  active: boolean
  created_at: string
  updated_at: string
}

export interface Conversation {
  id: string
  tenant_id: string
  channel: 'whatsapp' | 'web' | 'test' | 'telegram'
  customer_phone: string
  customer_name: string | null
  status: 'idle' | 'pending_human' | 'closed'
  state: 'idle' | 'collecting_service' | 'collecting_slot' | 'confirming' | 'booked' | 'pending_human' | 'resolved' | 'closed'
  assigned_to: string | null
  last_message_at: string | null
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  tenant_id: string
  conversation_id: string
  direction: 'in' | 'out'
  author_type: 'customer' | 'bot' | 'human' | 'system'
  author_id: string | null
  body: string
  external_id: string | null
  delivery_status: 'received' | 'queued' | 'sent' | 'delivered' | 'read' | 'failed'
  metadata_json: Record<string, unknown>
  created_at: string
}

export interface Booking {
  id: string
  tenant_id: string
  service_id: string
  resource_id: string
  conversation_id: string | null
  customer_name: string
  customer_phone: string
  customer_email: string | null
  start_at: string
  end_at: string
  status: 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'no_show'
  source: 'bot' | 'web' | 'admin' | 'import' | 'test'
  notes: string
  cancellation_reason: string | null
  idempotency_key: string | null
  google_event_id: string | null
  google_sync_status: 'disabled' | 'pending' | 'synced' | 'error'
  cancelled_at: string | null
  created_at: string
  updated_at: string
}

export interface HandoffAlert {
  id: string
  tenant_id: string
  conversation_id: string
  reason: string
  severity: 'low' | 'medium' | 'high' | 'urgent'
  status: 'pending' | 'in_progress' | 'resolved'
  assigned_to: string | null
  created_at: string
  taken_at: string | null
  resolved_at: string | null
  resolution_note: string | null
}

export interface AuditLog {
  id: string
  tenant_id: string
  actor_type: 'human' | 'bot' | 'system'
  actor_id: string | null
  action: string
  entity_type: string
  entity_id: string | null
  payload_json: Record<string, unknown>
  tool_calls: string | null
  created_at: string
}

export interface KnowledgeDocument {
  id: string
  tenant_id: string
  section: 'faqs' | 'catalog' | 'policies'
  source_type: string
  source_id: string
  title: string
  content_hash: string
  indexed_hash: string | null
  status: 'pending' | 'indexed' | 'stale' | 'error'
  chunk_count: number
  embedding_model: string | null
  last_indexed_at: string | null
  last_error: string | null
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ApiError {
  error: string
  code: number
  message: string
  request_id: string
  tenant_id: string | null
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface PaginationParams {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface FilterParams {
  search?: string
  status?: string
  active?: boolean
  category?: string
  [key: string]: any
}
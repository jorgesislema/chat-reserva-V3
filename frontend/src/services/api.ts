import api from '@/lib/api'
import type {
  Tenant,
  Service,
  Resource,
  Schedule,
  ScheduleException,
  FAQ,
  Policy,
  Conversation,
  Message,
  Booking,
  HandoffAlert,
  AuditLog,
  KnowledgeDocument,
  PaginatedResponse,
  ApiResponse,
} from '@/types'

// Tenant / Identity
export const identityApi = {
  get: () => api.get<ApiResponse<{ tenant: any }>>('/tenants/me/identity'),
  update: (data: Partial<any>) => api.put<ApiResponse<{ tenant: any }>>('/tenants/me/identity', data),
}

// Services
export const servicesApi = {
  list: (params?: { active?: boolean }) => api.get<{ services: any[] }>('/api/services', { params }),
  get: (id: string) => api.get<{ service: any }>(`/api/services/${id}`),
  create: (data: any) => api.post<{ service: any }>('/api/services', data),
  update: (id: string, data: any) => api.put<{ service: any }>(`/api/services/${id}`, data),
  delete: (id: string) => api.delete(`/api/services/${id}`),
}

// Resources
export const resourcesApi = {
  list: (params?: { active?: boolean }) => api.get<{ resources: any[] }>('/api/resources', { params }),
  get: (id: string) => api.get<{ resource: any }>(`/api/resources/${id}`),
  create: (data: any) => api.post<{ resource: any }>('/api/resources', data),
  update: (id: string, data: any) => api.put<{ resource: any }>(`/api/resources/${id}`, data),
  delete: (id: string) => api.delete(`/api/resources/${id}`),
  getSchedule: (id: string) => api.get<{ schedules: any[] }>(`/api/resources/${id}/schedule`),
  updateSchedule: (id: string, blocks: any[]) => api.put<{ schedules: any[] }>(`/api/resources/${id}/schedule`, { blocks }),
}

// Schedule Exceptions
export const exceptionsApi = {
  list: (params?: { resource_id?: string }) => api.get<{ exceptions: any[] }>('/api/schedule-exceptions', { params }),
  create: (data: any) => api.post<{ exception: any }>('/api/schedule-exceptions', data),
  get: (id: string) => api.get<{ exception: any }>(`/api/schedule-exceptions/${id}`),
  update: (id: string, data: any) => api.put<{ exception: any }>(`/api/schedule-exceptions/${id}`, data),
  delete: (id: string) => api.delete(`/api/schedule-exceptions/${id}`),
}

// FAQs
export const faqsApi = {
  list: (params?: { active?: boolean }) => api.get<{ faqs: any[] }>('/api/faqs', { params }),
  create: (data: any) => api.post<{ faq: any }>('/api/faqs', data),
  get: (id: string) => api.get<{ faq: any }>(`/api/faqs/${id}`),
  update: (id: string, data: any) => api.put<{ faq: any }>(`/api/faqs/${id}`, data),
  delete: (id: string) => api.delete(`/api/faqs/${id}`),
}

// Policies
export const policiesApi = {
  list: (params?: { active?: boolean }) => api.get<{ policies: any[] }>('/api/policies', { params }),
  get: (key: string) => api.get<{ policy: any }>(`/api/policies/${key}`),
  upsert: (data: any) => api.put<{ policy: any }>('/api/policies', data),
}

// Knowledge
export const knowledgeApi = {
  status: () => api.get<{ status: Record<string, any> }>('/api/knowledge/status'),
  reindex: (sections: string[]) => api.post<{ status: Record<string, any> }>('/api/knowledge/reindex', { sections }),
  test: (question: string) => api.post<{ answer: string | null; sources: any[]; note?: string }>('/api/knowledge/test', { question }),
}

// Conversations
export const conversationsApi = {
  create: (data: { customer_phone: string; customer_name?: string; disclosure_text: string }) =>
    api.post<{ conversation: any; ai_disclosure: any }>('/api/conversations', data),
  list: (params?: { status?: string; customer_phone?: string }) => api.get<{ conversations: any[] }>('/api/conversations', { params }),
  get: (id: string) => api.get<{ conversation: any }>(`/api/conversations/${id}`),
  getMessages: (id: string) => api.get<{ messages: any[] }>(`/api/conversations/${id}/messages`),
}

// Bookings
export const bookingsApi = {
  list: (params?: { status?: string; customer_phone?: string }) => api.get<{ bookings: any[] }>('/api/bookings', { params }),
  get: (id: string) => api.get<{ booking: any }>(`/api/bookings/${id}`),
  create: (data: any) => api.post<{ booking: any }>('/api/bookings', data),
  cancel: (id: string, reason: string) => api.post<{ booking: any }>(`/api/bookings/${id}/cancel`, { reason }),
  reschedule: (id: string, new_start_at: string) => api.post<{ booking: any }>(`/api/bookings/${id}/reschedule`, { new_start_at }),
}

// Handoff Alerts
export const alertsApi = {
  list: (params?: { status?: string }) => api.get<{ alerts: any[] }>('/api/alerts', { params }),
  get: (id: string) => api.get<{ alert: any }>(`/api/alerts/${id}`),
  take: (id: string, assigned_to: string) => api.post<{ alert: any }>(`/api/alerts/${id}/take`, { assigned_to }),
  resolve: (id: string, resolution_note: string, resolved_by: string) => api.post<{ alert: any }>(`/api/alerts/${id}/resolve`, { resolution_note, resolved_by }),
}

// Customers / Forget
export const customersApi = {
  forgetRequest: (id: string) => api.post<{ customer: any }>(`/api/customers/${id}/forget-request`),
  forgetExecute: (id: string) => api.post<{ customer: any }>(`/api/customers/${id}/forget-execute`),
}

// Data Retention
export const retentionApi = {
  expired: () => api.get<{ expired_messages: any[]; expired_customers: any[] }>('/api/data-retention', { params: { expired: true } }),
  purge: () => api.post<{ purged_at: string }>('/api/data-retention/purge'),
}

// Knowledge Test
export const knowledgeTestApi = {
  test: (question: string) => api.post<{ answer: string | null; sources: any[]; note?: string }>('/api/knowledge/test', { question }),
}

// Knowledge Reindex
export const knowledgeReindexApi = {
  reindex: (sections: string[]) => api.post<{ status: Record<string, any> }>('/api/knowledge/reindex', { sections }),
  status: () => api.get<{ status: Record<string, any> }>('/api/knowledge/status'),
}

// Audit Log
export const auditApi = {
  list: (params?: { action?: string; limit?: number; offset?: number }) => api.get<{ audit_log: any[] }>('/api/audit-log', { params }),
}

// Identity
export const identityApi = {
  get: () => api.get('/api/tenants/me/identity'),
  update: (data: any) => api.put('/api/tenants/me/identity', data),
}

// Services
export const servicesApi = {
  list: (params?: { active?: boolean }) => api.get('/api/services', { params }),
  get: (id: string) => api.get(`/api/services/${id}`),
  create: (data: any) => api.post('/api/services', data),
  update: (id: string, data: any) => api.put(`/api/services/${id}`, data),
  delete: (id: string) => api.delete(`/api/services/${id}`),
}

// Resources
export const resourcesApi = {
  list: (params?: { active?: boolean }) => api.get('/api/resources', { params }),
  get: (id: string) => api.get(`/api/resources/${id}`),
  create: (data: any) => api.post('/api/resources', data),
  update: (id: string, data: any) => api.put(`/api/resources/${id}`, data),
  delete: (id: string) => api.delete(`/api/resources/${id}`),
  getSchedule: (id: string) => api.get(`/api/resources/${id}/schedule`),
  updateSchedule: (id: string, blocks: any[]) => api.put(`/api/resources/${id}/schedule`, { blocks }),
}

// Schedule Exceptions
export const exceptionsApi = {
  list: (params?: { resource_id?: string }) => api.get('/api/schedule-exceptions', { params }),
  create: (data: any) => api.post('/api/schedule-exceptions', data),
  get: (id: string) => api.get(`/api/schedule-exceptions/${id}`),
  update: (id: string, data: any) => api.put(`/api/schedule-exceptions/${id}`, data),
  delete: (id: string) => api.delete(`/api/schedule-exceptions/${id}`),
}

// FAQs
export const faqsApi = {
  list: (params?: { active?: boolean }) => api.get('/api/faqs', { params }),
  create: (data: any) => api.post('/api/faqs', data),
  get: (id: string) => api.get(`/api/faqs/${id}`),
  update: (id: string, data: any) => api.put(`/api/faqs/${id}`, data),
  delete: (id: string) => api.delete(`/api/faqs/${id}`),
}

// Policies
export const policiesApi = {
  list: (params?: { active?: boolean }) => api.get('/api/policies', { params }),
  get: (key: string) => api.get(`/api/policies/${key}`),
  upsert: (data: any) => api.put('/api/policies', data),
}

// Knowledge
export const knowledgeApi = {
  status: () => api.get('/api/knowledge/status'),
  reindex: (sections: string[]) => api.post('/api/knowledge/reindex', { sections }),
  test: (question: string) => api.post('/api/knowledge/test', { question }),
}

// Conversations
export const conversationsApi = {
  create: (data: { customer_phone: string; customer_name?: string; disclosure_text: string }) =>
    api.post('/api/conversations', data),
  list: (params?: { status?: string; customer_phone?: string }) => api.get('/api/conversations', { params }),
  get: (id: string) => api.get(`/api/conversations/${id}`),
  getMessages: (id: string) => api.get(`/api/conversations/${id}/messages`),
}

// Bookings
export const bookingsApi = {
  list: (params?: { status?: string; customer_phone?: string }) => api.get('/api/bookings', { params }),
  get: (id: string) => api.get(`/api/bookings/${id}`),
  create: (data: any) => api.post('/api/bookings', data),
  cancel: (id: string, reason: string) => api.post(`/api/bookings/${id}/cancel`, { reason }),
  reschedule: (id: string, new_start_at: string) => api.post(`/api/bookings/${id}/reschedule`, { new_start_at }),
}

// Handoff Alerts
export const alertsApi = {
  list: (params?: { status?: string }) => api.get('/api/alerts', { params }),
  get: (id: string) => api.get(`/api/alerts/${id}`),
  take: (id: string, assigned_to: string) => api.post(`/api/alerts/${id}/take`, { assigned_to }),
  resolve: (id: string, resolution_note: string, resolved_by: string) => api.post(`/api/alerts/${id}/resolve`, { resolution_note, resolved_by }),
}

// Customers / Forget
export const customersApi = {
  forgetRequest: (id: string) => api.post(`/api/customers/${id}/forget-request`),
  forgetExecute: (id: string) => api.post(`/api/customers/${id}/forget-execute`),
}

// Data Retention
export const retentionApi = {
  expired: () => api.get('/api/data-retention', { params: { expired: true } }),
  purge: () => api.post('/api/data-retention/purge'),
}

// Knowledge Test
export const knowledgeTestApi = {
  test: (question: string) => api.post('/api/knowledge/test', { question }),
}

// Knowledge Reindex
export const knowledgeReindexApi = {
  reindex: (sections: string[]) => api.post('/api/knowledge/reindex', { sections }),
  status: () => api.get('/api/knowledge/status'),
}

// Audit Log
export const auditApi = {
  list: (params?: { action?: string; limit?: number; offset?: number }) => api.get('/api/audit-log', { params }),
}
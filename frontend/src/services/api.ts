'use client'

export interface ApiErrorShape {
  error?: string
  code?: number
  message?: string
  tenant_id?: string | null
  retry_after?: number
}

const DEFAULT_ERROR: ApiErrorShape = {
  error: 'unknown_error',
  code: 0,
  message: 'Error inesperado de red o servidor',
}

function toMessage(err: unknown): string {
  if (err && typeof err === 'object' && 'message' in err) {
    const m = (err as ApiErrorShape).message
    if (m) return m
  }
  return DEFAULT_ERROR.message || 'Error inesperado'
}

export class ApiClientError extends Error {
  status: number
  code: string
  retryAfter?: number
  constructor(status: number, payload: ApiErrorShape) {
    super(payload.message || payload.error || `HTTP ${status}`)
    this.status = status
    this.code = payload.error || 'unknown_error'
    if (typeof payload.retry_after === 'number') this.retryAfter = payload.retry_after
  }
}

const identityApi = {
  get: () => request<void, { tenant: any }>('/tenants/me/identity'),
  update: (data: any) => request<any, { tenant: any }>('/tenants/me/identity', 'PUT', data),
}

const servicesApi = {
  list: (params?: Record<string, unknown>) =>
    request<void, { services: any[] }>(withQuery('/services', params)),
  get: (id: string) => request<void, { service: any }>(`/services/${id}`),
  create: (data: any) => request<any, { service: any }>('/services', 'POST', data),
  update: (id: string, data: any) => request<any, { service: any }>(`/services/${id}`, 'PUT', data),
  remove: (id: string) => request<void, { ok: boolean }>(`/services/${id}`, 'DELETE'),
}

const resourcesApi = {
  list: () => request<void, { resources: any[] }>('/resources'),
  get: (id: string) => request<void, { resource: any }>(`/resources/${id}`),
  create: (data: any) => request<any, { resource: any }>('/resources', 'POST', data),
  update: (id: string, data: any) => request<any, { resource: any }>(`/resources/${id}`, 'PUT', data),
  remove: (id: string) => request<void, { ok: boolean }>(`/resources/${id}`, 'DELETE'),
  getSchedule: (id: string) => request<void, { schedules: any[] }>(`/resources/${id}/schedule`),
  updateSchedule: (id: string, blocks: any[]) =>
    request<any, { schedules: any[] }>(`/resources/${id}/schedule`, 'PUT', { schedule: blocks }),
}

const exceptionsApi = {
  list: () => request<void, { exceptions: any[] }>('/schedule-exceptions'),
  create: (data: any) => request<any, { exception: any }>('/schedule-exceptions', 'POST', data),
  update: (id: string, data: any) =>
    request<any, { exception: any }>(`/schedule-exceptions/${id}`, 'PUT', data),
  remove: (id: string) => request<void, { ok: boolean }>(`/schedule-exceptions/${id}`, 'DELETE'),
}

const faqsApi = {
  list: () => request<void, { faqs: any[] }>('/faqs'),
  get: (id: string) => request<void, { faq: any }>(`/faqs/${id}`),
  create: (data: any) => request<any, { faq: any }>('/faqs', 'POST', data),
  update: (id: string, data: any) => request<any, { faq: any }>(`/faqs/${id}`, 'PUT', data),
  remove: (id: string) => request<void, { ok: boolean }>(`/faqs/${id}`, 'DELETE'),
}

const policiesApi = {
  list: () => request<void, { policies: any[] }>('/policies'),
  upsert: (data: any) => request<any, { policy: any }>(`/policies/${data.key}`, 'PUT', data),
}

const knowledgeApi = {
  status: () => request<void, any>('/knowledge/status'),
  reindex: () => request<void, any>('/knowledge/reindex', 'POST'),
  test: (data: any) => request<any, any>('/knowledge/test', 'POST', data),
}

const conversationsApi = {
  create: (data: any) => request<any, { conversation: any }>('/conversations', 'POST', data),
  list: (params?: Record<string, unknown>) =>
    request<void, { conversations: any[] }>(withQuery('/conversations', params)),
  get: (id: string) => request<void, { conversation: any }>(`/conversations/${id}`),
  getMessages: (id: string) => request<void, { messages: any[] }>(`/conversations/${id}/messages`),
}

const bookingsApi = {
  list: (params?: Record<string, unknown>) =>
    request<void, { bookings: any[] }>(withQuery('/bookings', params)),
}

const alertsApi = {
  list: (params?: Record<string, unknown>) =>
    request<void, { alerts: any[] }>(withQuery('/alerts', params)),
  take: (id: string) => request<void, { alert: any }>(`/handoff/${id}/take`, 'POST'),
  resolve: (id: string, note: string) =>
    request<{ note: string }, { alert: any }>(`/handoff/${id}/resolve`, 'POST', { note }),
  close: (id: string) => request<void, { alert: any }>(`/handoff/${id}/close`, 'POST'),
}

const customersApi = {
  list: (params?: Record<string, unknown>) =>
    request<void, { customers: any[] }>(withQuery('/customers', params)),
  forgetRequest: (id: string) => request<void, any>(`/customers/${id}/forget-request`, 'POST'),
  forgetExecute: (id: string) => request<void, any>(`/customers/${id}/forget-execute`, 'POST'),
}

const retentionApi = {
  expired: () => request<void, { expired: any[] }>('/data-retention'),
  purge: () => request<void, any>('/data-retention/purge', 'POST'),
}

const auditApi = {
  list: () => request<void, { entries: any[] }>('/audit-log'),
}

const catalogApi = {
  list: () => request<void, { items: any[] }>('/catalog'),
  create: (data: any) => request<any, { item: any }>('/catalog', 'POST', data),
  update: (id: string, data: any) => request<any, { item: any }>(`/catalog/${id}`, 'PUT', data),
}

const templatesApi = {
  list: () => request<void, { templates: any[] }>('/templates'),
  create: (data: any) => request<any, { template: any }>('/templates', 'POST', data),
  update: (id: string, data: any) => request<any, { template: any }>(`/templates/${id}`, 'PUT', data),
}

const remindersApi = {
  dryRun: () => request<void, any>('/reminders/dry-run', 'POST'),
  execute: () => request<void, any>('/reminders/execute', 'POST'),
  attempts: () => request<void, { attempts: any[] }>('/reminders/attempts'),
}

const internalChatApi = {
  ask: (question: string) => request<{ question: string }, any>('/internal-chat', 'POST', { question }),
}

function withQuery(path: string, params?: Record<string, unknown>): string {
  if (!params) return path
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&')
  return qs ? `${path}?${qs}` : path
}

async function request<TBody, TResp>(
  path: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
  body?: TBody
): Promise<TResp> {
  const { apiFetch } = await import('@/lib/api')
  return apiFetch<TResp>(path, method, body)
}

export {
  identityApi,
  servicesApi,
  resourcesApi,
  exceptionsApi,
  faqsApi,
  policiesApi,
  knowledgeApi,
  conversationsApi,
  bookingsApi,
  alertsApi,
  customersApi,
  retentionApi,
  auditApi,
  catalogApi,
  templatesApi,
  remindersApi,
  internalChatApi,
  toMessage,
}

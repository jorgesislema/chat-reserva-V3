import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const MAX_RETRIES = 2
const MAX_BACKOFF_MS = 5000

function _currentApiKey(): string | null {
  return localStorage.getItem('saas_api_key')
}

function _isRetryable(method: string | undefined, status: number): boolean {
  // Solo las lecturas (GET) reintentan 429 con backoff acotado.
  // Las escrituras nunca se reenvían: un reintento podría duplicar un efecto.
  if (!method || method.toUpperCase() !== 'GET') return false
  return status === 429
}

function _backoffMs(retryAfterHeader: string | null, attempt: number): number {
  let ms = 1000 * 2 ** attempt
  if (retryAfterHeader) {
    const parsed = parseInt(retryAfterHeader, 10)
    if (Number.isFinite(parsed) && parsed > 0) ms = parsed * 1000
  }
  return Math.min(ms, MAX_BACKOFF_MS)
}

function _isCurrentSession(config: AxiosRequestConfig): boolean {
  const sentKey = (config.headers as Record<string, string> | undefined)?.['X-API-Key']
  return Boolean(sentKey) && sentKey === _currentApiKey()
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const apiKey = _currentApiKey()
    if (apiKey) {
      config.headers['X-API-Key'] = apiKey
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: number }

    const status = error.response?.status
    const retryAfter = (error.response?.headers as Record<string, string> | null)?.['retry-after'] ?? null

    if (status === 401) {
      // Un 401 real invalida la credencial que se usó. Si la respuesta llegó
      // de una sesión antigua (distinta apiKey), no se cierra la sesión nueva.
      if (_isCurrentSession(originalRequest)) {
        const { useAuthStore } = await import('@/lib/auth')
        useAuthStore.getState().logout()
        window.dispatchEvent(new CustomEvent('auth:unauthorized', { detail: { code: 401 } }))
      }
      return Promise.reject(error)
    }

    if (status === 403) {
      // Prohibido: credencial válida pero sin permiso. NO se cierra sesión.
      window.dispatchEvent(new CustomEvent('auth:forbidden', { detail: { code: 403 } }))
      return Promise.reject(error)
    }

    if (status === 429 && _isRetryable(originalRequest.method, status)) {
      const attempt = originalRequest._retry ?? 0
      if (attempt < MAX_RETRIES) {
        originalRequest._retry = attempt + 1
        const delay = _backoffMs(retryAfter, attempt)
        await new Promise((resolve) => setTimeout(resolve, delay))
        return api(originalRequest)
      }
    }

    return Promise.reject(error)
  }
)

export interface ApiEnvelope<T> {
  data: T
}

export async function apiFetch<TResp>(
  path: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' = 'GET',
  body?: unknown
): Promise<TResp> {
  const resp = await api.request<TResp>({
    url: path,
    method,
    data: body,
  })
  return resp.data
}

export function extractError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    const msg = (error.response?.data as { message?: string; error?: string } | undefined)
    if (status === 429) return 'Demasiadas peticiones. Espera unos segundos e intenta de nuevo.'
    if (status === 401) return 'Sesión no válida. Vuelve a identificarte.'
    if (status === 403) return 'No tienes permiso para esta operación.'
    if (status && status >= 500) return 'Error del servidor. Inténtalo de nuevo más tarde.'
    return msg?.message || msg?.error || error.message || 'Error de red'
  }
  return error instanceof Error ? error.message : 'Error inesperado'
}

export default api

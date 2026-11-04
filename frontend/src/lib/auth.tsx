import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { useEffect, useState, type ReactNode } from 'react'

export interface Tenant {
  id: string
  slug: string
  name: string
  timezone: string
  locale: string
  currency: string
  business_type: string | null
  labels: Record<string, string>
  settings: Record<string, unknown>
}

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'user'
}

interface AuthState {
  apiKey: string | null
  tenant: Tenant | null
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  setApiKey: (key: string) => void
  setTenant: (tenant: Tenant) => void
  setUser: (user: User) => void
  logout: () => void
  setLoading: (loading: boolean) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      apiKey: null,
      tenant: null,
      user: null,
      isAuthenticated: false,
      isLoading: true,
      setApiKey: (key: string) => {
        localStorage.setItem('saas_api_key', key)
        set({ apiKey: key, isAuthenticated: true })
      },
      setTenant: (tenant: Tenant) => set({ tenant }),
      setUser: (user: User) => set({ user }),
      logout: () => {
        localStorage.removeItem('saas_api_key')
        set({ apiKey: null, tenant: null, user: null, isAuthenticated: false })
      },
      setLoading: (loading: boolean) => set({ isLoading: loading }),
    }),
    {
      name: 'saas_auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        apiKey: state.apiKey,
        tenant: state.tenant,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

export const useAuth = () => {
  const { apiKey, tenant, user, isAuthenticated, isLoading, setApiKey, setTenant, setUser, logout, setLoading } = useAuthStore()
  return { apiKey, tenant, user, isAuthenticated, isLoading, setApiKey, setTenant, setUser, logout, setLoading }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { apiKey, setTenant, setLoading, logout, isAuthenticated } = useAuth()
  const [checked, setChecked] = useState(() => !apiKey)

  useEffect(() => {
    if (!apiKey) {
      setLoading(false)
      setChecked(true)
      return
    }
    let active = true
    setLoading(true)
    ;(async () => {
      try {
        const { identityApi } = await import('@/services/api')
        const resp = await identityApi.get()
        if (!active) return
        const t = resp.tenant
        setTenant({
          id: t.id,
          slug: t.slug,
          name: t.name,
          timezone: t.timezone,
          locale: t.locale,
          currency: t.currency,
          business_type: t.business_type,
          labels: t.labels_json ?? {},
          settings: t.settings_json ?? {},
        })
      } catch (err) {
        if (active) logout()
      } finally {
        if (active) {
          setLoading(false)
          setChecked(true)
        }
      }
    })()
    return () => {
      active = false
    }
  }, [apiKey, setTenant, setLoading, logout])

  if (checked && !isLoading) {
    return <>{children}</>
  }
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-text-secondary">Cargando...</p>
      </div>
    </div>
  )
}

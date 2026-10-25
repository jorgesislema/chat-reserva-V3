import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

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
      isLoading: false,
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
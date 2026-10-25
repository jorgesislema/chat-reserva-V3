import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { useEffect } from 'react'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading, logout } = useAuth()
  const location = useLocation()

  useEffect(() => {
    const handleAuthError = (event: CustomEvent) => {
      if (event.detail?.code === 'unauthorized') {
        logout()
      }
    }
    window.addEventListener('auth:unauthorized', handleAuthError as EventListener)
    return () => window.removeEventListener('auth:unauthorized', handleAuthError as EventListener)
  }, [logout])

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
          <p className="text-text-secondary">Cargando...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
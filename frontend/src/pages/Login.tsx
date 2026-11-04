'use client'

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { AlertCircle, Loader2, LayoutDashboard } from 'lucide-react'

export function Login() {
  const { setApiKey } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()
  const [apiKey, setApiKeyState] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')
    if (!apiKey.trim()) {
      setError('Ingresa tu API key')
      return
    }
    setIsLoading(true)

    try {
      const res = await fetch('/api/tenants/me/identity', {
        headers: {
          'X-API-Key': apiKey.trim(),
          'Content-Type': 'application/json',
        },
      })

      if (!res.ok) {
        if (res.status === 401) {
          throw new Error('API key inválida o expirada')
        }
        if (res.status === 429) {
          throw new Error('Demasiadas peticiones. Espera unos segundos.')
        }
        throw new Error('Error al validar la API key')
      }

      const data = await res.json()

      // Guarda la key y el tenant en el store persistido; el AuthProvider
      // verificará la identidad al montar. Navegación programática (no reload).
      setApiKey(apiKey.trim())
      if (data.tenant) {
        const { setTenant } = await import('@/lib/auth')
        setTenant(data.tenant)
      }
      navigate('/dashboard')
    } catch (err: any) {
      const msg = err?.message || 'Error al iniciar sesión'
      setError(msg)
      toast({ title: 'Error de autenticación', description: msg, variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface px-4 py-12">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-600 mb-6">
            <LayoutDashboard className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-text-primary mb-2">Bienvenido</h1>
          <p className="text-text-secondary">
            Ingresa tu API key para acceder al panel de administración
          </p>
        </div>

        <Card className="shadow-card">
          <CardHeader className="text-center">
            <CardTitle>Iniciar sesión</CardTitle>
            <CardDescription>
              Ingresa tu API key para acceder al panel de administración
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="apiKey" className="text-sm font-medium text-text-secondary">
                  API Key
                </Label>
                <Input
                  id="apiKey"
                  name="apiKey"
                  type="password"
                  placeholder="sk_live_..."
                  value={apiKey}
                  onChange={(e) => setApiKeyState(e.target.value)}
                  disabled={isLoading}
                  autoComplete="off"
                  autoFocus
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300 text-sm">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <Button type="submit" className="w-full" disabled={isLoading} loading={isLoading}>
                <Loader2 className="h-4 w-4 mr-2" />
                {isLoading ? 'Validando...' : 'Acceder'}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col gap-3 border-t pt-0">
            <p className="text-center text-sm text-text-muted">
              ¿No tienes API key?{' '}
              <Link to="/register" className="text-primary-600 hover:underline">
                Solicitar acceso
              </Link>
            </p>
          </CardFooter>
        </Card>

        <div className="mt-6 text-center text-sm text-text-muted">
          <p>Panel de administración SaaS • Multi-tenant nativo</p>
        </div>
      </div>
    </div>
  )
}

export { Login }

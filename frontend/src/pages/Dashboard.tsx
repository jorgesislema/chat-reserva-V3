'use client'

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Calendar, MessageSquare, TrendingUp, AlertTriangle } from 'lucide-react'
import { cn } from '@/utils'
import { formatRelativeTime } from '@/utils'
import { bookingsApi, alertsApi, conversationsApi } from '@/services/api'
import { extractError } from '@/lib/api'
import { useToast } from '@/hooks/use-toast'

interface KPI {
  label: string
  value: string
  icon: React.ReactNode
  color: string
}

function isToday(iso: string | null | undefined): boolean {
  if (!iso) return false
  const today = new Date().toISOString().slice(0, 10)
  return iso.slice(0, 10) === today
}

export function Dashboard() {
  const { toast } = useToast()
  const [kpis, setKpis] = useState<KPI[]>([
    { label: 'Reservas hoy', value: '—', icon: <Calendar className="h-5 w-5" />, color: 'text-blue-600 dark:text-blue-400' },
    { label: 'Alertas pendientes', value: '—', icon: <AlertTriangle className="h-5 w-5" />, color: 'text-yellow-600 dark:text-yellow-400' },
    { label: 'Conversaciones', value: '—', icon: <MessageSquare className="h-5 w-5" />, color: 'text-green-600 dark:text-green-400' },
  ])
  const [alertsActive, setAlertsActive] = useState(0)
  const [bookingsToday, setBookingsToday] = useState<any[]>([])
  const [recentActivity, setRecentActivity] = useState<Array<{
    id: string
    type: 'booking' | 'alert' | 'message'
    title: string
    time: string
    status: 'success' | 'warning' | 'info'
  }>>([])

  useEffect(() => {
    let active = true
    ;(async () => {
      try {
        const [bkResp, alResp, cvResp] = await Promise.all([
          bookingsApi.list(),
          alertsApi.list(),
          conversationsApi.list(),
        ])
        if (!active) return
        const todayBk = (bkResp.bookings || []).filter((b: any) => isToday(b.start_at))
        const pendingAlerts = (alResp.alerts || []).filter((a: any) => a.status === 'pending')
        const convs = cvResp.conversations || []
        setBookingsToday(todayBk)
        setAlertsActive(pendingAlerts.length)
        setKpis([
          { label: 'Reservas hoy', value: String(todayBk.length), icon: <Calendar className="h-5 w-5" />, color: 'text-blue-600 dark:text-blue-400' },
          { label: 'Alertas pendientes', value: String(pendingAlerts.length), icon: <AlertTriangle className="h-5 w-5" />, color: 'text-yellow-600 dark:text-yellow-400' },
          { label: 'Conversaciones', value: String(convs.length), icon: <MessageSquare className="h-5 w-5" />, color: 'text-green-600 dark:text-green-400' },
        ])

        const activity: typeof recentActivity = []
        pendingAlerts.slice(0, 3).forEach((a: any) => {
          activity.push({
            id: `a-${a.id}`,
            type: 'alert',
            title: `Handoff: ${a.reason || 'derivación pendiente'}`,
            time: formatRelativeTime(a.created_at),
            status: 'warning',
          })
        })
        todayBk.slice(0, 3).forEach((b: any) => {
          activity.push({
            id: `b-${b.id}`,
            type: 'booking',
            title: `${b.customer_name || 'Cliente'} — ${b.service_id || 'cita'}`,
            time: formatRelativeTime(b.start_at),
            status: 'success',
          })
        })
        setRecentActivity(activity)
      } catch (error) {
        if (active) toast({ title: 'Error', description: extractError(error), variant: 'error' })
      }
    })()
    return () => { active = false }
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-secondary mt-1">Bienvenido al panel de administración</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" asChild>
            <Link to="/config">Configuración</Link>
          </Button>
          <Button asChild>
            <Link to="/conversations">Ver conversaciones</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {kpis.map((kpi) => (
          <Card key={kpi.label} className="card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary">{kpi.label}</p>
                  <p className="text-3xl font-bold text-text-primary mt-1">{kpi.value}</p>
                </div>
                <div className={cn('p-3 rounded-xl bg-surface-elevated')}>
                  <span className={kpi.color}>{kpi.icon}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Actividad reciente
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentActivity.length === 0 ? (
              <p className="text-center py-8 text-text-muted">Sin actividad todavía</p>
            ) : (
              <div className="space-y-4">
                {recentActivity.map((activity) => (
                  <div key={activity.id} className="flex items-start gap-3 p-3 rounded-lg bg-surface-sunken/50">
                    <div className={cn(
                      'flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center',
                      activity.status === 'success' && 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
                      activity.status === 'warning' && 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
                      activity.status === 'info' && 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                    )}>
                      {activity.type === 'booking' && <Calendar className="h-5 w-5" />}
                      {activity.type === 'alert' && <AlertTriangle className="h-5 w-5" />}
                      {activity.type === 'message' && <MessageSquare className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate">{activity.title}</p>
                      <p className="text-xs text-text-muted mt-0.5">{activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Alertas de Handoff
            </CardTitle>
            <Badge variant={alertsActive > 0 ? 'warning' : 'success'}>
              {alertsActive} activas
            </Badge>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-text-secondary">
              {alertsActive > 0
                ? `Tienes ${alertsActive} derivaciones pendientes de atender.`
                : 'No hay derivaciones pendientes.'}
            </p>
          </CardContent>
          <div className="p-6 pt-0">
            <Button variant="outline" asChild className="w-full">
              <Link to="/alerts">Gestionar alertas</Link>
            </Button>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Citas de hoy
            </CardTitle>
          </CardHeader>
          <CardContent>
            {bookingsToday.length === 0 ? (
              <p className="text-center py-8 text-text-muted">No hay citas para hoy</p>
            ) : (
              <div className="space-y-3">
                {bookingsToday.map((appointment) => (
                  <div key={appointment.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-sunken/50">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30">
                        <Calendar className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                      </div>
                      <div>
                        <p className="font-medium text-text-primary">{appointment.start_at?.slice(11, 16) || '—'}</p>
                        <p className="text-sm text-text-secondary">
                          {appointment.customer_name || 'Cliente'} • {appointment.service_id || 'servicio'}
                        </p>
                      </div>
                    </div>
                    <Badge variant={appointment.status === 'confirmed' ? 'success' : 'warning'}>
                      {appointment.status === 'confirmed' ? 'Confirmada' : 'Pendiente'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Métricas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-text-secondary">
              Las métricas detalladas (conversión, no-show, tiempos de respuesta) requieren
              datos históricos acumulados; se muestran aquí cuando estén disponibles.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export { Dashboard }

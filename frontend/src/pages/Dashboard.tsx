'use client'

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { LayoutDashboard, Users, Calendar, MessageSquare, TrendingUp, AlertTriangle, Clock, CheckCircle, XCircle, TrendingDown } from 'lucide-react'
import { cn } from '@/utils'
import { formatRelativeTime, formatCurrency } from '@/utils'

interface KPI {
  label: string
  value: string | number
  change?: number
  trend?: 'up' | 'down' | 'neutral'
  icon: React.ReactNode
  color: string
}

interface AlertSummary {
  pending: number
  inProgress: number
  resolvedToday: number
}

export function Dashboard() {
  const [kpis, setKpis] = useState<KPI[]>([
    { label: 'Reservas hoy', value: '12', change: 12, trend: 'up', icon: <Calendar className="h-5 w-5" />, color: 'text-blue-600 dark:text-blue-400' },
    { label: 'Clientes nuevos', value: '3', change: 50, trend: 'up', icon: <Users className="h-5 w-5" />, color: 'text-green-600 dark:text-green-400' },
    { label: 'Alertas pendientes', value: '2', change: -33, trend: 'down', icon: <AlertTriangle className="h-5 w-5" />, color: 'text-yellow-600 dark:text-yellow-400' },
    { label: 'Tasa conversión', value: '68%', change: 5, trend: 'up', icon: <TrendingUp className="h-5 w-5" />, color: 'text-purple-600 dark:text-purple-400' },
  ])

  const [alerts, setAlerts] = useState<AlertSummary>({
    pending: 2,
    inProgress: 1,
    resolvedToday: 5,
  })

  const [recentActivity, setRecentActivity] = useState<Array<{
    id: string
    type: 'booking' | 'alert' | 'message'
    title: string
    time: string
    status: 'success' | 'warning' | 'info'
  }>([
    { id: '1', type: 'booking', title: 'Nueva reserva: Consulta dental - María García', time: 'Hace 5 min', status: 'success' },
    { id: '2', type: 'alert', title: 'Handoff solicitado: Juan Pérez quiere hablar con humano', time: 'Hace 15 min', status: 'warning' },
    { id: '3', type: 'booking', title: 'Reserva confirmada: Limpieza dental - Carlos Ruiz', time: 'Hace 1 hora', status: 'success' },
    { id: '3', type: 'message', title: 'Mensaje entrante: "¿Cuál es el horario?"', time: 'Hace 2 horas', status: 'info' },
  ])

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
          </Link>
          <Button asChild>
            <Link to="/conversations">Ver conversaciones</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {kpis.map((kpi) => (
          <Card key={kpi.label} className="card-hover">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-text-secondary">{kpi.label}</p>
                  <p className="text-3xl font-bold text-text-primary mt-1">{kpi.value}</p>
                </div>
                <div className={cn(
                  'p-3 rounded-xl',
                  kpi.color.replace('text-', 'bg-').replace('dark:text-', 'dark:bg-') + '/10'
                )}>
                  <span className={kpi.color}><kpi.icon /></span>
                </div>
              </div>
              {kpi.change !== undefined && (
                <div className="mt-4 flex items-center gap-1">
                  <span className={cn(
                    'text-sm font-medium',
                    kpi.trend === 'up' ? 'text-green-600' : kpi.trend === 'down' ? 'text-red-600' : 'text-text-muted'
                  )}>
                    {kpi.trend === 'up' && <TrendingUp className="h-3.5 w-3.5" />}
                    {kpi.trend === 'down' && <TrendingDown className="h-3.5 w-3.5" />}
                    {Math.abs(kpi.change)}%
                  </span>
                  <span className="text-sm text-text-muted">vs mes anterior</span>
                </div>
              )}
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
            <div className="space-y-4">
              {recentActivity.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3 p-3 rounded-lg bg-surface-sunken/50">
                  <div className={cn(
                    'flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center',
                    activity.status === 'success' && 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
                    activity.status === 'warning' && 'bg-yellow-100 text-yellow-600 dark:bg-yellow-900/30 dark:text-yellow-400',
                    activity.status === 'info' && 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                  )}>
                    {activity.type === 'booking' && <CheckCircle className="h-5 w-5" />}
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
          </CardContent>
          <CardFooter className="border-t border-border">
            <Button variant="ghost" asChild className="w-full">
              <Link to="/conversations">Ver toda la actividad</Link>
            </Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Alertas de Handoff
            </CardTitle>
            <Badge variant={alerts.pending > 0 ? 'warning' : 'success'}>
              {alerts.pending + alerts.inProgress} activas
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-yellow-50 dark:bg-yellow-900/20">
                  <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{alerts.pending}</p>
                  <p className="text-xs text-text-muted">Pendientes</p>
                </div>
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <p className="text-2xl font-bold text-blue-600 dark:text-blue-400">{alerts.inProgress}</p>
                  <p className="text-xs text-text-muted">En progreso</p>
                </div>
                <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/20">
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">{alerts.resolvedToday}</p>
                  <p className="text-xs text-text-muted">Resueltas hoy</p>
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <Button variant="outline" asChild className="w-full">
              <Link to="/alerts">Gestionar alertas</Link>
            </Button>
          </CardFooter>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Próximas citas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { time: '09:00', service: 'Consulta dental', resource: 'Dra. Ana', status: 'confirmed' },
                { time: '10:30', service: 'Limpieza dental', resource: 'Dr. Luis', status: 'pending' },
                { time: '12:00', service: 'Blanqueamiento', resource: 'Dra. Ana', status: 'confirmed' },
              ].map((appointment, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-surface-sunken/50">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
                      <Clock className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                    </div>
                    <div>
                      <p className="font-medium text-text-primary">{appointment.time}</p>
                      <p className="text-sm text-text-secondary">{appointment.service} • {appointment.resource}</p>
                    </div>
                  </div>
                  <Badge variant={appointment.status === 'confirmed' ? 'success' : 'warning'}>
                    {appointment.status === 'confirmed' ? 'Confirmada' : 'Pendiente'}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
          <CardFooter>
            <Button variant="ghost" asChild className="w-full">
              <Link to="/schedules">Ver agenda completa</Link>
            </Button>
          </CardFooter>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Métricas rápidas
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-surface-sunken/50">
                <p className="text-xs text-text-muted">Tasa no-show</p>
                <p className="text-2xl font-bold text-text-primary">8%</p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">↓ 2% vs mes anterior</p>
              </div>
              <div className="p-4 rounded-lg bg-surface-sunken/50">
                <p className="text-xs text-text-muted">Tiempo medio respuesta</p>
                <p className="text-2xl font-bold text-text-primary">3 min</p>
                <p className="text-xs text-red-600 dark:text-red-400 mt-1">↑ 1 min vs mes anterior</p>
              </div>
              <div className="p-4 rounded-lg bg-surface-sunken/50">
                <p className="text-xs text-text-muted">Clientes recurrentes</p>
                <p className="text-2xl font-bold text-text-primary">65%</p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">↑ 3% vs mes anterior</p>
              </div>
              <div className="p-4 rounded-lg bg-surface-sunken/50">
                <p className="text-xs text-text-muted">Ingresos mes actual</p>
                <p className="text-2xl font-bold text-text-primary">€12,450</p>
                <p className="text-xs text-green-600 dark:text-green-400 mt-1">↑ 15% vs mes anterior</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export { Dashboard }
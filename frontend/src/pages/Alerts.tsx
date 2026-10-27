'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AlertTriangle } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { alertsApi } from '@/services/api'
import { extractError } from '@/lib/api'
import { formatRelativeTime } from '@/utils'

interface Alert {
  id: string
  reason: string
  severity: 'low' | 'medium' | 'high' | 'urgent'
  status: 'pending' | 'in_progress' | 'resolved'
  created_at: string
  conversation?: {
    customer_name: string | null
    customer_phone: string
  }
}

export function Alerts() {
  const { toast } = useToast()
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState('all')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)
  const [resolutionNote, setResolutionNote] = useState('')

  const fetchAlerts = async () => {
    setIsLoading(true)
    try {
      const response = await alertsApi.list(
        statusFilter !== 'all' ? { status: statusFilter } : undefined
      )
      setAlerts(response.alerts || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
  }, [statusFilter])

  const handleTake = async (alert: Alert) => {
    try {
      await alertsApi.take(alert.id)
      toast({ title: 'Alerta tomada', variant: 'success' })
      fetchAlerts()
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const handleResolve = async () => {
    if (!selectedAlert || !resolutionNote.trim()) return
    try {
      await alertsApi.resolve(selectedAlert.id, resolutionNote)
      toast({ title: 'Alerta resuelta', variant: 'success' })
      setDialogOpen(false)
      setResolutionNote('')
      setSelectedAlert(null)
      fetchAlerts()
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const openResolveDialog = (alert: Alert) => {
    setSelectedAlert(alert)
    setResolutionNote('')
    setDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Alertas de Handoff</h1>
          <p className="text-text-secondary mt-1">Gestiona las derivaciones a humano</p>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-4">
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Alertas de Handoff
          </CardTitle>
          <div className="flex items-center gap-2">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]"><SelectValue placeholder="Todos los estados" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="pending">Pendientes</SelectItem>
                <SelectItem value="in_progress">En progreso</SelectItem>
                <SelectItem value="resolved">Resueltas</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Motivo</TableHead>
                  <TableHead>Severidad</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Creada</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8">
                      <div className="flex justify-center gap-2">
                        <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-text-muted">Cargando...</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : alerts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-text-muted">
                      No hay alertas
                    </TableCell>
                  </TableRow>
                ) : (
                  alerts.map((alert) => (
                    <TableRow key={alert.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{alert.conversation?.customer_name || 'Sin nombre'}</p>
                          <p className="text-sm text-text-muted">{alert.conversation?.customer_phone}</p>
                        </div>
                      </TableCell>
                      <TableCell className="max-w-xs truncate">{alert.reason}</TableCell>
                      <TableCell>
                        <Badge variant={
                          alert.severity === 'urgent' || alert.severity === 'high' ? 'destructive' :
                          alert.severity === 'medium' ? 'warning' : 'secondary'
                        }>
                          {alert.severity}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={
                          alert.status === 'pending' ? 'warning' :
                          alert.status === 'in_progress' ? 'secondary' : 'success'
                        }>
                          {alert.status === 'pending' ? 'Pendiente' :
                          alert.status === 'in_progress' ? 'En progreso' : 'Resuelta'}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatRelativeTime(alert.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {alert.status === 'pending' && (
                            <Button size="sm" onClick={() => handleTake(alert)}>Tomar</Button>
                          )}
                          {alert.status === 'in_progress' && (
                            <Button size="sm" variant="outline" onClick={() => openResolveDialog(alert)}>Resolver</Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Resolver alerta</DialogTitle>
            <DialogDescription>
              Escribe una nota de resolución para la alerta de{' '}
              <strong>{selectedAlert?.conversation?.customer_name || 'este cliente'}</strong>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="resolution_note">Nota de resolución *</Label>
              <Textarea
                id="resolution_note"
                value={resolutionNote}
                onChange={e => setResolutionNote(e.target.value)}
                placeholder="Describe cómo se resolvió el caso..."
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialogOpen(false); setResolutionNote(''); setSelectedAlert(null); }}>
              Cancelar
            </Button>
            <Button onClick={handleResolve} disabled={!resolutionNote.trim()}>
              Marcar como resuelta
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { Alerts }

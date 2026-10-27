'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Calendar, Plus, Clock, Trash2, Edit } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { resourcesApi } from '@/services/api'
import { extractError } from '@/lib/api'

interface ScheduleBlock {
  weekday: number
  start_time: string
  end_time: string
}

interface Resource {
  id: string
  name: string
}

export function Schedules() {
  const { toast } = useToast()
  const [resources, setResources] = useState<Resource[]>([])
  const [selectedResource, setSelectedResource] = useState<string>('')
  const [schedules, setSchedules] = useState<ScheduleBlock[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingBlock, setEditingBlock] = useState<ScheduleBlock | null>(null)
  const [formData, setFormData] = useState({ weekday: 0, start_time: '09:00', end_time: '10:00' })

  const fetchResources = async () => {
    try {
      const response = await resourcesApi.list()
      setResources(response.resources || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const fetchSchedules = async () => {
    if (!selectedResource) return
    setIsLoading(true)
    try {
      const response = await resourcesApi.getSchedule(selectedResource)
      setSchedules(response.schedules || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchResources()
  }, [])

  useEffect(() => {
    if (selectedResource) {
      fetchSchedules()
    } else {
      setSchedules([])
    }
  }, [selectedResource])

  const handleAddBlock = () => {
    setEditingBlock(null)
    setFormData({ weekday: 0, start_time: '09:00', end_time: '10:00' })
    setDialogOpen(true)
  }

  const handleSubmit = async () => {
    if (!selectedResource) return
    try {
      const blocks = editingBlock
        ? schedules.map(b =>
            b.weekday === editingBlock.weekday && b.start_time === editingBlock.start_time
              ? { ...formData }
              : b
          )
        : [...schedules, formData]

      await resourcesApi.updateSchedule(selectedResource, blocks)
      toast({ title: editingBlock ? 'Franja actualizada' : 'Franja agregada', variant: 'success' })
      setDialogOpen(false)
      setEditingBlock(null)
      setFormData({ weekday: 0, start_time: '09:00', end_time: '10:00' })
      fetchSchedules()
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const handleDelete = async (weekday: number, start_time: string) => {
    if (!confirm('¿Eliminar esta franja?')) return
    if (!selectedResource) return
    try {
      const blocks = schedules.filter(b => !(b.weekday === weekday && b.start_time === start_time))
      await resourcesApi.updateSchedule(selectedResource, blocks)
      toast({ title: 'Franja eliminada', variant: 'success' })
      fetchSchedules()
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const openEdit = (block: ScheduleBlock) => {
    setEditingBlock(block)
    setFormData({ weekday: block.weekday, start_time: block.start_time, end_time: block.end_time })
    setDialogOpen(true)
  }

  const weekdays = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Horarios</h1>
          <p className="text-text-secondary mt-1">Configura las franjas horarias de tus recursos</p>
        </div>
        <Button onClick={handleAddBlock} disabled={!selectedResource}>
          <Plus className="h-4 w-4 mr-2" />
          Agregar franja
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Configuración de horarios
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="resource">Recurso</Label>
              <Select value={selectedResource} onValueChange={setSelectedResource}>
                <SelectTrigger><SelectValue placeholder="Selecciona un recurso" /></SelectTrigger>
                <SelectContent>
                  {resources.map(r => (
                    <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {selectedResource && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Horarios de {resources.find(r => r.id === selectedResource)?.name || 'recurso'}
            </CardTitle>
            <Button onClick={handleAddBlock} disabled={isLoading}>
              <Plus className="h-4 w-4 mr-2" />
              Agregar franja
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8"><div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin" /></div>
            ) : schedules.length === 0 ? (
              <div className="text-center py-8 text-text-muted">
                No hay franjas configuradas. Haz clic en "Agregar franja" para empezar.
              </div>
            ) : (
              <div className="space-y-2">
                {weekdays.map((day, dayIndex) => {
                  const daySchedules = schedules.filter(s => s.weekday === dayIndex)
                  if (daySchedules.length === 0) return null
                  return (
                    <div key={dayIndex} className="border border-border rounded-lg overflow-hidden">
                      <div className="px-4 py-2 bg-surface-elevated font-medium text-text-secondary">
                        {day}
                      </div>
                      <div className="divide-y divide-border">
                        {daySchedules.map((schedule, i) => (
                          <div key={i} className="flex items-center justify-between px-4 py-3 hover:bg-surface-sunken/50">
                            <div className="flex items-center gap-3">
                              <Clock className="h-5 w-5 text-text-muted" />
                              <span className="font-medium">{schedule.start_time} - {schedule.end_time}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Button variant="ghost" size="sm" onClick={() => openEdit(schedule)}>
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="sm" className="text-red-600" onClick={() => handleDelete(schedule.weekday, schedule.start_time)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingBlock ? 'Editar franja' : 'Nueva franja horaria'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="weekday">Día de la semana</Label>
              <Select
                value={formData.weekday.toString()}
                onValueChange={v => setFormData({ ...formData, weekday: parseInt(v, 10) })}
              >
                <SelectTrigger><SelectValue placeholder="Selecciona día" /></SelectTrigger>
                <SelectContent>
                  {weekdays.map((day, i) => (
                    <SelectItem key={i} value={i.toString()}>{day}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_time">Hora inicio</Label>
                <Input id="start_time" type="time" value={formData.start_time} onChange={e => setFormData({ ...formData, start_time: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_time">Hora fin</Label>
                <Input id="end_time" type="time" value={formData.end_time} onChange={e => setFormData({ ...formData, end_time: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialogOpen(false); setEditingBlock(null); setFormData({ weekday: 0, start_time: '09:00', end_time: '10:00' }); }}>
              Cancelar
            </Button>
            <Button onClick={handleSubmit} disabled={isLoading}>
              {editingBlock ? 'Actualizar' : 'Agregar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { Schedules }

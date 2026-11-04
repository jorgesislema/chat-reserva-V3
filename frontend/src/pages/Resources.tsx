'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, Edit, Trash2, Users } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { resourcesApi } from '@/services/api'
import { extractError } from '@/lib/api'
import type { Resource } from '@/types'

export function Resources() {
  const { toast } = useToast()
  const [resources, setResources] = useState<Resource[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingResource, setEditingResource] = useState<Resource | null>(null)
  const [formData, setFormData] = useState({ name: '', email: '', kind: 'professional' })

  const fetchResources = async () => {
    setIsLoading(true)
    try {
      const response = await resourcesApi.list()
      setResources(response.resources || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchResources()
  }, [])

  const handleCreate = async () => {
    setIsSaving(true)
    try {
      const response = await resourcesApi.create(formData)
      setResources(prev => [...prev, response.resource])
      toast({ title: 'Recurso creado', variant: 'success' })
      setDialogOpen(false)
      setFormData({ name: '', email: '', kind: 'professional' })
    } catch (error) {
      toast({ title: 'Error al crear', description: extractError(error), variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleUpdate = async () => {
    if (!editingResource) return
    setIsSaving(true)
    try {
      const response = await resourcesApi.update(editingResource.id, formData)
      setResources(prev => prev.map(r => r.id === editingResource.id ? response.resource : r))
      toast({ title: 'Recurso actualizado', variant: 'success' })
      setDialogOpen(false)
      setEditingResource(null)
      setFormData({ name: '', email: '', kind: 'professional' })
    } catch (error) {
      toast({ title: 'Error al actualizar', description: extractError(error), variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('¿Estás seguro de que quieres eliminar este recurso?')) return
    try {
      await resourcesApi.remove(id)
      setResources(prev => prev.filter(r => r.id !== id))
      toast({ title: 'Recurso eliminado', variant: 'success' })
    } catch (error) {
      toast({ title: 'Error al eliminar', description: extractError(error), variant: 'error' })
    }
  }

  const openCreateDialog = () => {
    setEditingResource(null)
    setFormData({ name: '', email: '', kind: 'professional' })
    setDialogOpen(true)
  }

  const openEditDialog = (resource: Resource) => {
    setEditingResource(resource)
    setFormData({ name: resource.name, email: resource.email || '', kind: resource.kind })
    setDialogOpen(true)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Recursos</h1>
          <p className="text-text-secondary mt-1">Gestiona profesionales, salas y equipos</p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="h-4 w-4 mr-2" />
          Nuevo recurso
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Lista de recursos
          </CardTitle>
          <CardDescription>Profesionales, salas y equipos</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-text-muted">Cargando...</TableCell>
                  </TableRow>
                ) : resources.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-text-muted">
                      No hay recursos todavía
                    </TableCell>
                  </TableRow>
                ) : (
                  resources.map((resource) => (
                    <TableRow key={resource.id}>
                      <TableCell className="font-medium">{resource.name}</TableCell>
                      <TableCell>
                        <Badge variant={resource.kind === 'professional' ? 'primary' : 'secondary'}>
                          {resource.kind === 'professional' ? 'Profesional' : resource.kind}
                        </Badge>
                      </TableCell>
                      <TableCell>{resource.email || '—'}</TableCell>
                      <TableCell>
                        <Badge variant={resource.active ? 'success' : 'secondary'}>
                          {resource.active ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="sm" onClick={() => openEditDialog(resource)}>
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="sm" className="text-red-600" onClick={() => handleDelete(resource.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
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
            <DialogTitle>{editingResource ? 'Editar recurso' : 'Nuevo recurso'}</DialogTitle>
            <DialogDescription>Datos del profesional, sala o equipo</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nombre</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Nombre del recurso"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="email@ejemplo.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kind">Tipo</Label>
              <Select value={formData.kind} onValueChange={(v) => setFormData({ ...formData, kind: v })}>
                <SelectTrigger id="kind"><SelectValue placeholder="Selecciona tipo" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="professional">Profesional</SelectItem>
                  <SelectItem value="room">Sala</SelectItem>
                  <SelectItem value="equipment">Equipo</SelectItem>
                  <SelectItem value="other">Otro</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDialogOpen(false); setEditingResource(null); setFormData({ name: '', email: '', kind: 'professional' }); }}>
              Cancelar
            </Button>
            <Button onClick={editingResource ? handleUpdate : handleCreate} disabled={isSaving} loading={isSaving}>
              {editingResource ? 'Actualizar' : 'Crear'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { Resources }

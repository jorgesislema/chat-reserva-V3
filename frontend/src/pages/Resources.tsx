'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell, TableFooter } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Plus, Edit, Trash2, MoreHorizontal } from 'lucide-react'
import { useState } from 'react'
import { useToast } from '@/hooks/use-toast'
import { resourcesApi } from '@/services/api'
import { cn } from '@/utils'
import { Resource } from '@/types'

export function Resources() {
  const { toast } = useToast()
  const [resources, setResources] = useState<Resource[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingResource, setEditingResource] = useState<Resource | null>(null)
  const [formData, setFormData] = useState({ name: '', email: '', kind: 'professional' })

  const fetchResources = async () => {
    setIsLoading(true)
    try {
      const response = await resourcesApi.list()
      setResources(response.resources || [])
    } catch (error: any) {
      console.error(error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCreate = async () => {
    try {
      const resource = await resourcesApi.create(formData)
      setResources(prev => [...prev, resource])
      toast({ title: 'Recurso creado', variant: 'success' })
      setDialogOpen(false)
      setFormData({ name: '', email: '', kind: 'professional' })
    } catch (error: any) {
      toast({ title: 'Error al crear', description: error.message, variant: 'error' })
    }
  }

  const handleUpdate = async () => {
    if (!editingResource) return
    try {
      const updated = await resourcesApi.update(editingResource.id, formData)
      setResources(prev => prev.map(r => r.id === editingResource.id ? updated : r))
      toast({ title: 'Recurso actualizado', variant: 'success' })
      setDialogOpen(false)
      setEditingResource(null)
      setFormData({ name: '', email: '', kind: 'professional' })
    } catch (error: any) {
      toast({ title: 'Error al actualizar', description: error.message, variant: 'error' })
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('¿Estás seguro de que quieres eliminar este recurso?')) return
    try {
      await resourcesApi.delete(id)
      setResources(prev => prev.filter(r => r.id !== id))
      toast({ title: 'Recurso eliminado', variant: 'success' })
    } catch (error: any) {
      toast({ title: 'Error al eliminar', description: error.message, variant: 'error' })
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
          <CardDescription>Gestiona profesionales, salas y equipos</CardDescription>
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
                {resources.map((resource) => (
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
                        <Button variant="ghost" size="sm" variant="destructive" onClick={() => handleDelete(resource.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingResource ? 'Editar recurso' : 'Nuevo recurso'}</DialogTitle>
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
                <SelectTrigger><SelectValue placeholder="Selecciona tipo" /></SelectTrigger>
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
            <Button onClick={editingResource ? handleUpdate : handleCreate} disabled={isLoading} loading={isLoading}>
              {editingResource ? 'Actualizar' : 'Crear'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { Resources }
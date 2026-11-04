'use client'

import { useState, useEffect } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { LayoutDashboard, Package, Users, Calendar, HelpCircle, Save, Plus } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { identityApi, catalogApi, faqsApi, policiesApi } from '@/services/api'
import { extractError } from '@/lib/api'

interface CatalogItem {
  id: string
  name: string
  type: 'tratamiento' | 'producto'
  description: string
  observations: string
  inventory: number | null
  price_cents: number
  active: boolean
}

export function Config() {
  const { toast } = useToast()
  const [activeTab, setActiveTab] = useState('identity')
  const [isSaving, setIsSaving] = useState(false)
  const [identity, setIdentity] = useState({
    name: '',
    business_type: '',
    timezone: 'Europe/Madrid',
    locale: 'es-ES',
    currency: 'EUR',
    labels: { service: 'Tratamiento', resource: 'Profesional', booking: 'Cita', customer: 'Paciente' },
    settings: { onboarding_completed: true, public_booking: true, handoff_sound: false },
  })

  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [faqs, setFaqs] = useState<any[]>([])
  const [policies, setPolicies] = useState<any[]>([])
  const [newItem, setNewItem] = useState<Partial<CatalogItem>>({
    name: '',
    type: 'tratamiento',
    description: '',
    price_cents: 0,
    inventory: null,
  })

  const tabs = [
    { id: 'identity', label: 'Identidad', icon: <LayoutDashboard className="h-4 w-4" /> },
    { id: 'services', label: 'Servicios', icon: <Package className="h-4 w-4" /> },
    { id: 'resources', label: 'Recursos', icon: <Users className="h-4 w-4" /> },
    { id: 'schedules', label: 'Horarios', icon: <Calendar className="h-4 w-4" /> },
    { id: 'faqs', label: 'FAQs', icon: <HelpCircle className="h-4 w-4" /> },
    { id: 'policies', label: 'Políticas', icon: <HelpCircle className="h-4 w-4" /> },
  ]

  const loadIdentidad = async () => {
    try {
      const resp = await identityApi.get()
      const t = resp.tenant
      const labels = t.labels_json || t.labels || {}
      const settings = t.settings_json || t.settings || {}
      setIdentity({
        name: t.name || '',
        business_type: t.business_type || '',
        timezone: t.timezone || 'Europe/Madrid',
        locale: t.locale || 'es-ES',
        currency: t.currency || 'EUR',
        labels: {
          service: labels.service || 'Tratamiento',
          resource: labels.resource || 'Profesional',
          booking: labels.booking || 'Cita',
          customer: labels.customer || 'Paciente',
        },
        settings: {
          onboarding_completed: settings.onboarding_completed ?? true,
          public_booking: settings.public_booking ?? true,
          handoff_sound: settings.handoff_sound ?? false,
        },
      })
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const loadCatalog = async () => {
    try {
      const resp = await catalogApi.list()
      setCatalog(resp.items || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const loadFaqs = async () => {
    try {
      const resp = await faqsApi.list()
      setFaqs(resp.faqs || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  const loadPolicies = async () => {
    try {
      const resp = await policiesApi.list()
      setPolicies(Array.isArray(resp.policies) ? resp.policies : [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    }
  }

  useEffect(() => {
    if (activeTab === 'identity') loadIdentidad()
    if (activeTab === 'services') loadCatalog()
    if (activeTab === 'faqs') loadFaqs()
    if (activeTab === 'policies') loadPolicies()
  }, [activeTab])

  const handleSaveIdentity = async () => {
    setIsSaving(true)
    try {
      await identityApi.update({
        name: identity.name,
        business_type: identity.business_type || null,
        timezone: identity.timezone,
        locale: identity.locale,
        currency: identity.currency,
        labels: identity.labels,
        settings: identity.settings,
      })
      toast({ title: 'Identidad actualizada', variant: 'success' })
    } catch (error) {
      toast({ title: 'Error al guardar', description: extractError(error), variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const handleCreateItem = async () => {
    if (!newItem.name || !newItem.type) return
    setIsSaving(true)
    try {
      await catalogApi.create({
        name: newItem.name,
        type: newItem.type,
        description: newItem.description || '',
        price_cents: Number(newItem.price_cents) || 0,
        inventory: newItem.inventory == null ? null : Number(newItem.inventory),
      })
      toast({ title: 'Artículo creado', variant: 'success' })
      setNewItem({ name: '', type: 'tratamiento', description: '', price_cents: 0, inventory: null })
      loadCatalog()
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Configuración</h1>
          <p className="text-text-secondary mt-1">Gestiona la configuración de tu negocio</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-6">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id} className="flex items-center justify-center gap-2">
              {tab.icon}
              <span>{tab.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="identity" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Identidad del negocio</CardTitle>
              <CardDescription>Configura la información básica de tu negocio</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Nombre del negocio</Label>
                  <Input
                    id="name"
                    value={identity.name}
                    onChange={(e) => setIdentity({ ...identity, name: e.target.value })}
                    placeholder="Clínica Dental Demo"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="business_type">Tipo de negocio</Label>
                  <Select value={identity.business_type} onValueChange={(v) => setIdentity({ ...identity, business_type: v })}>
                    <SelectTrigger><SelectValue placeholder="Selecciona..." /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="dental_clinic">Clínica dental</SelectItem>
                      <SelectItem value="beauty_salon">Salón de belleza</SelectItem>
                      <SelectItem value="auto_repair">Taller mecánico</SelectItem>
                      <SelectItem value="consulting">Consultoría</SelectItem>
                      <SelectItem value="other">Otro</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Zona horaria</Label>
                  <Select value={identity.timezone} onValueChange={(v) => setIdentity({ ...identity, timezone: v })}>
                    <SelectTrigger><SelectValue placeholder="Zona horaria" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Europe/Madrid">Madrid (CET)</SelectItem>
                      <SelectItem value="America/Mexico_City">Ciudad de México (CST)</SelectItem>
                      <SelectItem value="America/Bogota">Bogotá (COT)</SelectItem>
                      <SelectItem value="America/Lima">Lima (PET)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="currency">Moneda</Label>
                  <Select value={identity.currency} onValueChange={(v) => setIdentity({ ...identity, currency: v })}>
                    <SelectTrigger><SelectValue placeholder="Moneda" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="EUR">Euro (EUR)</SelectItem>
                      <SelectItem value="USD">Dólar estadounidense (USD)</SelectItem>
                      <SelectItem value="MXN">Peso mexicano (MXN)</SelectItem>
                      <SelectItem value="COP">Peso colombiano (COP)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-4 pt-4 border-t border-border">
                <h3 className="font-medium text-text-primary">Terminología personalizada</h3>
                <div className="grid gap-4 md:grid-cols-4">
                  <div className="space-y-2">
                    <Label htmlFor="label_service">Servicio (singular)</Label>
                    <Input
                      id="label_service"
                      value={identity.labels.service}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, service: e.target.value } })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="label_resource">Recurso (singular)</Label>
                    <Input
                      id="label_resource"
                      value={identity.labels.resource}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, resource: e.target.value } })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="label_booking">Cita (singular)</Label>
                    <Input
                      id="label_booking"
                      value={identity.labels.booking}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, booking: e.target.value } })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="label_customer">Cliente (singular)</Label>
                    <Input
                      id="label_customer"
                      value={identity.labels.customer}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, customer: e.target.value } })}
                    />
                  </div>
                </div>

                <div className="space-y-4 pt-4 border-t border-border">
                  <h3 className="font-medium text-text-primary">Configuración</h3>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label>Onboarding completado</Label>
                      <p className="text-sm text-text-muted">Mostrar wizard en primer acceso</p>
                    </div>
                    <Switch
                      checked={identity.settings.onboarding_completed}
                      onCheckedChange={(checked) => setIdentity({ ...identity, settings: { ...identity.settings, onboarding_completed: checked } })}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label>Reserva pública</Label>
                      <p className="text-sm text-text-muted">Permitir reservas sin autenticación</p>
                    </div>
                    <Switch
                      checked={identity.settings.public_booking}
                      onCheckedChange={(checked) => setIdentity({ ...identity, settings: { ...identity.settings, public_booking: checked } })}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <Label>Sonido en alertas handoff</Label>
                      <p className="text-sm text-text-muted">Reproducir sonido al recibir alerta</p>
                    </div>
                    <Switch
                      checked={identity.settings.handoff_sound}
                      onCheckedChange={(checked) => setIdentity({ ...identity, settings: { ...identity.settings, handoff_sound: checked } })}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={handleSaveIdentity} disabled={isSaving} loading={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                Guardar cambios
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>

        <TabsContent value="services">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Catálogo de servicios y productos</h2>
              <Button onClick={handleCreateItem} disabled={isSaving || !newItem.name} loading={isSaving}>
                <Plus className="h-4 w-4 mr-2" />
                Nuevo artículo
              </Button>
            </div>
            <Card>
              <CardHeader>
                <CardTitle>Nuevo artículo</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-4 md:grid-cols-6">
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="item_name">Nombre *</Label>
                  <Input id="item_name" value={newItem.name || ''}
                    onChange={(e) => setNewItem({ ...newItem, name: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="item_type">Tipo</Label>
                  <Select value={newItem.type || 'tratamiento'}
                    onValueChange={(v) => setNewItem({ ...newItem, type: v as CatalogItem['type'] })}>
                    <SelectTrigger id="item_type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tratamiento">Tratamiento</SelectItem>
                      <SelectItem value="producto">Producto</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="item_price">Precio (céntimos)</Label>
                  <Input id="item_price" type="number" value={newItem.price_cents ?? 0}
                    onChange={(e) => setNewItem({ ...newItem, price_cents: Number(e.target.value) })} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="item_inventory">Inventario</Label>
                  <Input id="item_inventory" type="number" value={newItem.inventory ?? ''}
                    onChange={(e) => setNewItem({ ...newItem, inventory: e.target.value === '' ? null : Number(e.target.value) })} />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="item_desc">Detalles</Label>
                  <Input id="item_desc" value={newItem.description || ''}
                    onChange={(e) => setNewItem({ ...newItem, description: e.target.value })} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Artículos existentes</CardTitle>
                <CardDescription>Columnas: detalle, observaciones, inventario y tipo</CardDescription>
              </CardHeader>
              <CardContent>
                {catalog.length === 0 ? (
                  <p className="text-center py-6 text-text-muted">No hay artículos todavía</p>
                ) : (
                  <div className="space-y-2">
                    {catalog.map((item) => (
                      <div key={item.id} className="flex items-center justify-between p-3 rounded-lg bg-surface-sunken/50">
                        <div>
                          <p className="font-medium">{item.name}</p>
                          <p className="text-sm text-text-muted">{item.description || 'Sin detalles'}</p>
                        </div>
                        <div className="flex items-center gap-3 text-sm">
                          <span className="text-text-secondary">{item.type}</span>
                          <span className="text-text-secondary">{(item.price_cents / 100).toLocaleString('es-ES', { style: 'currency', currency: identity.currency || 'EUR' })}</span>
                          {item.inventory != null && <span className="text-text-secondary">Stock: {item.inventory}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="resources">
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Recursos</h2>
            <p className="text-text-muted">Gestiona los profesionales y recursos en el apartado «Recursos» del menú.</p>
          </div>
        </TabsContent>

        <TabsContent value="schedules">
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Horarios</h2>
            <p className="text-text-muted">Configura las franjas horarias de cada recurso en el apartado «Horarios» del menú.</p>
          </div>
        </TabsContent>

        <TabsContent value="faqs">
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Preguntas frecuentes</h2>
            {faqs.length === 0 ? (
              <p className="text-text-muted">No hay preguntas frecuentes todavía.</p>
            ) : (
              <div className="space-y-2">
                {faqs.map((f: any) => (
                  <div key={f.id} className="p-3 rounded-lg bg-surface-sunken/50">
                    <p className="font-medium">{f.question}</p>
                    <p className="text-sm text-text-muted">{f.answer}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="policies">
          <div className="space-y-4">
            <h2 className="text-xl font-bold">Políticas</h2>
            {policies.length === 0 ? (
              <p className="text-text-muted">No hay políticas configuradas todavía.</p>
            ) : (
              <div className="space-y-2">
                {policies.map((p: any) => (
                  <div key={p.key} className="p-3 rounded-lg bg-surface-sunken/50">
                    <p className="font-medium">{p.key}</p>
                    <p className="text-sm text-text-muted">{typeof p.value === 'string' ? p.value : JSON.stringify(p.value)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export { Config }

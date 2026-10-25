'use client'

import { useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tab, TabList, TabPanel, TabTrigger } from '@/components/ui/tabs'
import { LayoutDashboard, Package, Users, Calendar, HelpCircle, Save, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useToast } from '@/hooks/use-toast'
import { identityApi, servicesApi, resourcesApi, schedulesApi, faqsApi, policiesApi, knowledgeApi } from '@/services/api'
import { cn } from '@/utils'

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

  const tabs = [
    { id: 'identity', label: 'Identidad', icon: <LayoutDashboard className="h-4 w-4" /> },
    { id: 'services', label: 'Servicios', icon: <Package className="h-4 w-4" /> },
    { id: 'resources', label: 'Recursos', icon: <Users className="h-4 w-4" /> },
    { id: 'schedules', label: 'Horarios', icon: <Calendar className="h-4 w-4" /> },
    { id: 'faqs', label: 'FAQs', icon: <HelpCircle className="h-4 w-4" /> },
    { id: 'policies', label: 'Políticas', icon: <HelpCircle className="h-4 w-4" /> },
  ]

  const handleSave = async (tab: string) => {
    setIsSaving(true)
    try {
      if (tab === 'identity') {
        await identityApi.update(identity)
        toast({ title: 'Identidad actualizada', variant: 'success' })
      }
      // TODO: implement other tabs
      toast({ title: 'Cambios guardados', variant: 'success' })
    } catch (error: any) {
      toast({ title: 'Error al guardar', description: error.message, variant: 'error' })
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
              <tab.icon />
              <span>{tab.label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="identity" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LayoutDashboard className="h-5 w-5" />
                Identidad del negocio
              </CardTitle>
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
                      <SelectItem value="America/Argentina/Buenos_Aires">Buenos Aires (ART)</SelectItem>
                      <SelectItem value="America/Caracas">Caracas (VET)</SelectItem>
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
                      <SelectItem value="PEN">Sol peruano (PEN)</SelectItem>
                      <SelectItem value="ARS">Peso argentino (ARS)</SelectItem>
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
                    <Label htmlFor="label_services">Servicios (plural)</Label>
                    <Input
                      id="label_services"
                      value={identity.labels.services}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, services: e.target.value } })}
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
                    <Label htmlFor="label_resources">Recursos (plural)</Label>
                    <Input
                      id="label_resources"
                      value={identity.labels.resources}
                      onChange={(e) => setIdentity({ ...identity, labels: { ...identity.labels, resources: e.target.value } })}
                    />
                  </div>
                </div>

                <div className="space-y-4 pt-4 border-t border-border">
                  <h3 className="font-medium text-text-primary">Configuración</h3>
                  <div className="space-y-4">
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
              </div>
            </CardContent>
            <CardFooter>
              <Button onClick={() => handleSave('identity')} disabled={isSaving} loading={isSaving}>
                <Save className="h-4 w-4 mr-2" />
                Guardar cambios
              </Button>
            </CardFooter>
          </Card>
        </TabsContent>

        {/* Other tabs would go here - simplified for brevity */}
        <TabsContent value="services">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Catálogo de servicios</h2>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Nuevo servicio
              </Button>
            </div>
            <p className="text-text-muted">Gestiona tu catálogo de servicios aquí</p>
          </div>
        </TabsContent>

        <TabsContent value="resources">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Recursos</h2>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Nuevo recurso
              </Button>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="schedules">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Horarios</h2>
            </div>
            <p className="text-text-muted">Configura los horarios de tus recursos aquí</p>
          </div>
        </TabsContent>

        <TabsContent value="faqs">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Preguntas frecuentes</h2>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Nueva FAQ
              </Button>
            </div>
            <p className="text-text-muted">Gestiona las preguntas frecuentes aquí</p>
          </div>
        </TabsContent>

        <TabsContent value="policies">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Políticas</h2>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Nueva política
              </Button>
            </div>
            <p className="text-text-muted">Configura las políticas de tu negocio aquí</p>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export { Config }
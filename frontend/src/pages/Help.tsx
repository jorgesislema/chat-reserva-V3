'use client'

import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Search, ExternalLink, ChevronDown, ChevronUp, HelpCircle, Shield, Lock, Users, Mail, Phone, Globe } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils'

const faqs = [
  {
    category: 'General',
    items: [
      { q: '¿Cómo configuro mi negocio por primera vez?', a: 'Al iniciar sesión por primera vez, se te guiará a través de un wizard de 5 pasos: Identidad, Catálogo, Recursos, Horarios y FAQs/Políticas. Completa cada paso y guarda los cambios.' },
      { q: '¿Puedo cambiar la terminología (ej. "Paciente" vs "Cliente")?', a: 'Sí, en Configuración > Identidad > Terminología personalizada puedes cambiar: Servicio/Servicios, Recurso/Recursos, Cita/Citas, Paciente/Pacientes.' },
      { q: '¿Cómo agrego un nuevo profesional?', a: 'Ve a Configuración > Recursos > Nuevo recurso. Selecciona "Profesional" como tipo e ingresa nombre y email.' },
    ]
  },
  {
    category: 'Reservas',
    items: [
      { q: '¿Cómo configuro los horarios de atención?', a: 'En Configuración > Horarios, selecciona un recurso y agrega franjas horarias por día de la semana. Puedes tener múltiples franjas por día.' },
      { q: '¿Puedo bloquear días festivos?', a: 'Sí, en Configuración > Excepciones puedes agregar días cerrados, horarios especiales o feriados.' },
      { q: '¿Cómo evito doble reserva?', a: 'El sistema previene automáticamente solapamientos. Si un cliente intenta reservar un horario ocupado, se le notifica que no está disponible.' },
    ]
  },
  {
    category: 'Bot y IA',
    items: [
      { q: '¿Cómo entreno al bot con mis FAQs?', a: 'En Configuración > FAQs, agrega tus preguntas y respuestas. Luego ve a Conocimiento > Reindexar y selecciona "faqs" para actualizar el conocimiento del bot.' },
      { q: '¿El bot puede derivar a humano?', a: 'Sí, si el cliente pide "hablar con una persona" o el bot no entiende tras 3 intentos, se crea una alerta de handoff en el dashboard.' },
      { q: '¿Puedo probar el bot antes de activarlo?', a: 'Sí, usa el botón "Probar mi bot" en la página de Conocimiento. Es un chat simulado que no consume WhatsApp.' },
    ]
  },
  {
    category: 'Cuenta y Facturación',
    items: [
      { q: '¿Cómo cambio mi plan?', a: 'Por ahora solo hay un plan. Contacta a soporte para cambios.' },
      { q: '¿Cómo cancelo mi suscripción?', a: 'Contacta a soporte desde la sección Ayuda. Procesaremos la cancelación en 24h.' },
      { q: '¿Dónde veo mis facturas?', a: 'En Configuración > Facturación (próximamente disponible).' },
    ]
  },
]

export function Help() {
  const [search, setSearch] = useState('')

  const filteredFaqs = faqs.flatMap(category =>
    category.items
      .filter(item => item.q.toLowerCase().includes(search.toLowerCase()) || item.a.toLowerCase().includes(search.toLowerCase()))
      .map(item => ({ ...item, category: category.category }))
  )

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold text-text-primary">Centro de Ayuda</h1>
        <p className="text-text-secondary mt-2">Encuentra respuestas a tus preguntas o contacta con soporte</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-text-muted" />
            <input
              type="text"
              placeholder="Buscar en la ayuda..."
              className="w-full pl-10 pr-4 py-3 border border-border rounded-lg bg-surface focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
              placeholder="Buscar en la ayuda..."
              onChange={e => {}}
            />
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4">
        {faqs.map(category => (
          <Card key={category.category} className="overflow-hidden">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2">
                <HelpCircle className="h-5 w-5 text-primary-600 dark:text-primary-400" />
                {category.category}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-3">
                {category.items.map((item, i) => (
                  <details key={i} className="group border border-border rounded-lg overflow-hidden">
                    <summary className="flex items-center justify-between p-4 cursor-pointer hover:bg-surface-sunken/50 transition-colors list-none">
                      <p className="font-medium text-text-primary pr-8">{item.q}</p>
                      <ChevronDown className="h-5 w-5 text-text-muted transition-transform duration-200 group-open:rotate-180" />
                    </summary>
                    <div className="px-4 pb-4 text-text-secondary leading-relaxed">
                      {item.a}
                    </div>
                  </details>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="border-t border-border pt-8">
        <h2 className="text-xl font-bold text-text-primary mb-4">¿No encontraste lo que buscabas?</h2>
        <div className="grid gap-4 md:grid-cols-3 mt-4">
          <Card className="p-6 text-center hover:shadow-card-hover transition-shadow">
            <Mail className="h-10 w-10 mx-auto text-primary-600 dark:text-primary-400 mb-3" />
            <h3 className="font-semibold text-text-primary mb-1">Email</h3>
            <p className="text-text-secondary text-sm mb-3">soporte@saas-reservas.com</p>
            <Button variant="outline" className="w-full" asChild>
              <a href="mailto:soporte@saas-reservas.com">Escribir email</a>
            </Button>
          </Card>
          <Card className="p-6 text-center hover:shadow-card-hover transition-shadow">
            <Phone className="h-10 w-10 mx-auto text-primary-600 dark:text-primary-400 mb-3" />
            <h3 className="font-semibold text-text-primary mb-1">Teléfono</h3>
            <p className="text-text-secondary text-sm mb-3">+34 900 123 456</p>
            <p className="text-xs text-text-muted">Lunes a Viernes 9:00 - 18:00</p>
          </Card>
          <Card className="p-6 text-center hover:shadow-card-hover transition-shadow">
            <Globe className="h-10 w-10 mx-auto text-primary-600 dark:text-primary-400 mb-3" />
            <h3 className="font-semibold text-text-primary mb-1">Documentación</h3>
            <p className="text-text-secondary text-sm mb-3">Guías, API docs y tutoriales</p>
            <Button variant="outline" className="w-full" asChild>
              <a href="/docs" target="_blank" rel="noopener noreferrer">Ver docs</a>
            </Button>
          </Card>
        </div>
      </div>
    </div>
  )
}

export { Help }
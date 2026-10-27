'use client'

import { useState, useEffect } from 'react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Search, MessageSquare } from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { conversationsApi } from '@/services/api'
import { extractError } from '@/lib/api'
import { formatRelativeTime } from '@/utils'

interface Conversation {
  id: string
  channel: string
  customer_phone: string
  customer_name: string | null
  status: string
  last_message_at: string | null
}

export function Conversations() {
  const { toast } = useToast()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  const fetchConversations = async () => {
    setIsLoading(true)
    try {
      const response = await conversationsApi.list(
        statusFilter !== 'all' ? { status: statusFilter } : undefined
      )
      setConversations(response.conversations || [])
    } catch (error) {
      toast({ title: 'Error', description: extractError(error), variant: 'error' })
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchConversations()
  }, [statusFilter])

  const filteredConversations = conversations.filter((c) => {
    if (!search) return true
    const needle = search.toLowerCase()
    return (
      c.customer_name?.toLowerCase().includes(needle) ||
      c.customer_phone.toLowerCase().includes(needle)
    )
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Conversaciones</h1>
          <p className="text-text-secondary mt-1">Gestiona las conversaciones con tus clientes</p>
        </div>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between flex-wrap gap-4">
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Conversaciones
          </CardTitle>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted" />
              <Input
                placeholder="Buscar por nombre o teléfono..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-10 w-64"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[180px]"><SelectValue placeholder="Todos los estados" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="idle">Inactivas</SelectItem>
                <SelectItem value="pending_human">Pendientes humano</SelectItem>
                <SelectItem value="booked">Con reserva</SelectItem>
                <SelectItem value="closed">Cerradas</SelectItem>
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
                  <TableHead>Canal</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Último mensaje</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <div className="flex justify-center gap-2">
                        <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
                        <span className="text-text-muted">Cargando...</span>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : filteredConversations.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-text-muted">
                      No se encontraron conversaciones
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredConversations.map((conv) => (
                    <TableRow key={conv.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{conv.customer_name || 'Sin nombre'}</p>
                          <p className="text-sm text-text-muted">{conv.customer_phone}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={conv.channel === 'whatsapp' ? 'primary' : conv.channel === 'web' ? 'secondary' : 'outline'}>
                          {conv.channel}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={
                          conv.status === 'pending_human' ? 'warning' :
                          conv.status === 'closed' ? 'secondary' :
                          'success'
                        }>
                          {conv.status === 'pending_human' ? 'Pendiente humano' :
                          conv.status === 'booked' ? 'Con reserva' :
                          conv.status === 'idle' ? 'Inactiva' : 'Cerrada'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {conv.last_message_at ? formatRelativeTime(conv.last_message_at) : 'Sin mensajes'}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" onClick={() => toast({ title: 'Detalle de conversación', description: `ID: ${conv.id}`, variant: 'default' })}>
                          Ver
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export { Conversations }

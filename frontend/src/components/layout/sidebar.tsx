'use client'

import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/utils'
import { LayoutDashboard, Settings, Users, Calendar, MessageSquare, Bell, HelpCircle } from 'lucide-react'
import { useAuth } from '@/lib/auth'

interface SidebarProps {
  collapsed?: boolean
}

export function Sidebar({ collapsed = false }: SidebarProps) {
  const location = useLocation()
  const { tenant } = useAuth()

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'Configuración', href: '/config', icon: Settings },
    { name: 'Recursos', href: '/resources', icon: Users },
    { name: 'Horarios', href: '/schedules', icon: Calendar },
    { name: 'Conversaciones', href: '/conversations', icon: MessageSquare },
    { name: 'Alertas', href: '/alerts', icon: Bell },
    { name: 'Ayuda', href: '/help', icon: HelpCircle },
  ]

  return (
    <aside
      className={cn(
        'fixed left-0 top-16 z-40 h-[calc(100vh-4rem)] w-[260px] bg-surface border-r border-border transition-all duration-300 ease-in-out flex flex-col overflow-y-auto overflow-x-hidden',
        collapsed && '-translate-x-full'
      )}
    >
      <div className="flex flex-col h-full">
        <div className="p-4 border-b border-border">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <LayoutDashboard className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg text-text-primary">SaaS Admin</span>
          </Link>
        </div>

        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          <ul className="space-y-1" role="navigation" aria-label="Navegación principal">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href || location.pathname.startsWith(item.href + '/')
              return (
                <li key={item.name}>
                  <Link
                    to={item.href}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                      'hover:bg-surface-elevated',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
                      isActive && 'bg-primary-100 text-primary-800 dark:bg-primary-900/30 dark:text-primary-200'
                    )}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <item.icon className={cn('h-5 w-5 flex-shrink-0', isActive ? 'text-primary-700 dark:text-primary-300' : 'text-text-muted')} aria-hidden="true" />
                    <span className="font-medium">{item.name}</span>
                    {item.href === '/config' && (
                      <span className="ml-auto px-1.5 py-0.5 text-xs font-medium rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300">
                        Config
                      </span>
                    )}
                  </Link>
                </li>
              )
            })}
          </ul>
        </nav>

        <div className="p-4 border-t border-border">
          <div className="text-xs text-text-muted text-center">{tenant?.name || 'SaaS Admin'}</div>
          <div className="text-xs text-text-muted text-center mt-1">v2.0.0</div>
        </div>
      </div>
    </aside>
  )
}

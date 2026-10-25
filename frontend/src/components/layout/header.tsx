'use client'

import { Link, useLocation } from 'react-router-dom'
import { Menu, X, Bell, LogOut, Settings, HelpCircle, Sun, Moon, LayoutDashboard } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/utils'
import { useAuth } from '@/lib/auth'
import { useTheme } from '@/lib/theme'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/hooks/use-toast'

export function Header() {
  const { isAuthenticated, tenant, logout, user } = useAuth()
  const { theme, setTheme, resolvedTheme } = useTheme()
  const { toast } = useToast()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showNotifications, setShowNotifications] = useState(false)

  const isSidebar = location.pathname.startsWith('/admin') || location.pathname.startsWith('/dashboard')

  const handleLogout = () => {
    logout()
    toast({ title: 'Sesión cerrada', description: 'Hasta pronto', variant: 'success' })
  }

  if (!isAuthenticated) return null

  const notificationCount = 3

  return (
    <header className={cn(
      'sticky top-0 z-40 w-full border-b border-border bg-surface/95 backdrop-blur supports-[backdrop-filter]:bg-surface/80',
      'transition-all duration-200'
    )}>
      <div className="container flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-surface-elevated"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Abrir menú"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>

          <Link to={isSidebar ? '/dashboard' : '/'} className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center">
              <LayoutDashboard className="w-5 h-5 text-white" />
            </div>
            <span className="hidden font-bold text-xl text-text-primary sm:block">
              SaaS Admin
            </span>
          </Link>

          {isSidebar && (
            <nav className="hidden md:flex items-center gap-1 ml-4">
              <Link to="/dashboard" className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                location.pathname === '/dashboard' ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'text-text-secondary hover:text-text-primary hover:bg-surface-elevated'
              )}>
                Dashboard
              </Link>
              <Link to="/config" className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                location.pathname.startsWith('/config') ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'text-text-secondary hover:text-text-primary hover:bg-surface-elevated'
              )}>
                Configuración
              </Link>
              <Link to="/conversations" className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                location.pathname.startsWith('/conversations') ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300' : 'text-text-secondary hover:text-text-primary hover:bg-surface-elevated'
              )}>
                Conversaciones
              </Link>
            </nav>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
            className="p-2 rounded-lg hover:bg-surface-elevated transition-colors"
            aria-label={resolvedTheme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
          >
            {resolvedTheme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="relative p-2 rounded-lg hover:bg-surface-elevated transition-colors" aria-label="Notificaciones">
                <Bell className="h-5 w-5" />
                {notificationCount > 0 && (
                  <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs font-medium text-white">
                    {notificationCount > 9 ? '9+' : notificationCount}
                  </span>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <div className="px-4 py-3 border-b border-border">
                <p className="font-medium text-text-primary">Notificaciones</p>
              </div>
              <DropdownMenuItem className="text-red-600 focus:text-red-600" onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Cerrar sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-surface-elevated transition-colors">
                <div className="w-8 h-8 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="end" forceMount>
              <div className="px-4 py-3 border-b border-border">
                <p className="font-medium text-text-primary">{user?.name || 'Usuario'}</p>
                <p className="text-sm text-text-muted">{user?.email}</p>
              </div>
              <DropdownMenuItem onClick={() => { /* navigate to profile */ }}>
                <Settings className="mr-2 h-4 w-4" />
                Perfil
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-red-600 focus:text-red-600">
                <LogOut className="mr-2 h-4 w-4" />
                Cerrar sesión
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
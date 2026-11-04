'use client'

import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/sidebar'
import { Header } from '@/components/layout/header'

export function Layout() {
  return (
    <div className="min-h-screen bg-surface flex">
      <Sidebar collapsed={false} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

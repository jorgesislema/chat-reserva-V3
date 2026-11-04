import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { AuthGuard } from '@/components/auth/AuthGuard'
import { Dashboard } from '@/pages/Dashboard'
import { Config } from '@/pages/Config'
import { Resources } from '@/pages/Resources'
import { Schedules } from '@/pages/Schedules'
import { Conversations } from '@/pages/Conversations'
import { Alerts } from '@/pages/Alerts'
import { Help } from '@/pages/Help'
import { Login } from '@/pages/Login'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/*"
        element={
          <AuthGuard>
            <Layout />
          </AuthGuard>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="config" element={<Config />} />
        <Route path="resources" element={<Resources />} />
        <Route path="schedules" element={<Schedules />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="help" element={<Help />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

export default App

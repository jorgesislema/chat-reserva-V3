import { Routes, Route, Navigate } from 'react-router-dom'
import { Suspense, lazy } from 'react'
import { Layout } from '@/components/layout/Layout'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const Config = lazy(() => import('@/pages/Config'))
const Resources = lazy(() => import('@/pages/Resources'))
const Schedules = lazy(() => import('@/pages/Schedules'))
const Conversations = lazy(() => import('@/pages/Conversations'))
const Alerts = lazy(() => import('@/pages/Alerts'))
const Help = lazy(() => import('@/pages/Help'))
const Login = lazy(() => import('@/pages/Login'))

function LoadingFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-surface">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-text-secondary">Cargando...</p>
      </div>
    </div>
  )
}

export function App() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/*"
          element={
            <Suspense fallback={<LoadingFallback />}>
              <Layout />
            </Suspense>
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
        <Route path="/login" element={<Login />} />
      </Routes>
    </Suspense>
  )
}

export default App
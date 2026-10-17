import { Routes, Route, Navigate } from 'react-router-dom'
import { LogIngestion } from '@/pages/LogIngestion'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Incidents } from '@/pages/Incidents'
import { Jobs } from '@/pages/Jobs'
import { ClusterStatus } from '@/pages/ClusterStatus'
import { Patterns } from '@/pages/Patterns'
import { Nodes } from '@/pages/Nodes'
import { Login } from '@/pages/Login'
import { ProtectedRoute } from '@/components/ProtectedRoute'

function App() {
  console.log('App component - rendering')
  console.log('App - Imports loaded:', {
    Layout: !!Layout,
    Dashboard: !!Dashboard,
    Incidents: !!Incidents,
    Jobs: !!Jobs,
    ClusterStatus: !!ClusterStatus,
    Login: !!Login,
    ProtectedRoute: !!ProtectedRoute
  })
  
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }>
        <Route index element={<Dashboard />} />
        <Route path="incidents" element={<Incidents />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="patterns" element={<Patterns />} />
        <Route path="nodes" element={<Nodes />} />
        <Route path="cluster" element={<ClusterStatus />} />
        <Route path="ingest" element={<LogIngestion />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App

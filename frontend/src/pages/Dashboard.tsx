import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { apiService } from '@/services/api'
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Upload,
  XCircle,
  Server,
  FileText
} from 'lucide-react'
import toast from 'react-hot-toast'
import { FallbackDashboard } from '@/components/FallbackDashboard'

export function Dashboard() {
  console.log('Dashboard component - rendering')
  const navigate = useNavigate()

  const [autoRefresh, setAutoRefresh] = useState(true) // Enable auto-refresh for real-time updates

  // ─────────────────────────────────────────────────────────────────────────────
  // Data fetching (React Query) - with shorter timeout and better error handling
  // ─────────────────────────────────────────────────────────────────────────────
  const {
    data: incidentsData,
    isLoading: incidentsLoading,
    error: incidentsError,
    refetch: refetchIncidents,
  } = useQuery({
    queryKey: ['incidents', { limit: 10, skip: 0 }],
    queryFn: () => apiService.getIncidents({ limit: 10, skip: 0 }),
    refetchInterval: autoRefresh ? 5_000 : false, // 5 second interval for real-time updates
    retry: 1,
    staleTime: 1000 * 60 * 5, // Longer stale time
    enabled: true, // Always enabled but with better error handling
  })

  const {
    data: jobsData,
    isLoading: jobsLoading,
    error: jobsError,
    refetch: refetchJobs,
  } = useQuery({
    queryKey: ['jobs', { limit: 10, skip: 0 }],
    queryFn: () => apiService.getJobs({ limit: 10, skip: 0 }),
    refetchInterval: autoRefresh ? 5_000 : false, // 5 second interval for real-time updates
    retry: 1,
    staleTime: 1000 * 60 * 5, // Longer stale time
    enabled: true,
  })

  const {
    data: clusterStatus,
    isLoading: clusterLoading,
    error: clusterError,
    refetch: refetchCluster,
  } = useQuery({
    queryKey: ['cluster', 'status'],
    queryFn: () => apiService.getClusterStatus(),
    refetchInterval: autoRefresh ? 10_000 : false, // 10 seconds for cluster
    retry: 1,
    staleTime: 1000 * 60 * 10, // Much longer stale time
    enabled: true,
  })

  const {
    data: health,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiService.healthCheck(),
    refetchInterval: autoRefresh ? 10_000 : false, // 10 seconds for health
    retry: 1,
    staleTime: 1000 * 60 * 10, // Longer stale time
    enabled: true,
  })

  // ─────────────────────────────────────────────────────────────────────────────
  // Normalization helpers (handle various response shapes)
  // ─────────────────────────────────────────────────────────────────────────────
  const incidents: any[] =
    Array.isArray((incidentsData as any)?.incidents) ? (incidentsData as any).incidents :
    Array.isArray((incidentsData as any)?.data)      ? (incidentsData as any).data :
    Array.isArray(incidentsData as any)              ? (incidentsData as any) :
    []

  const jobs: any[] =
    Array.isArray((jobsData as any)?.jobs) ? (jobsData as any).jobs :
    Array.isArray((jobsData as any)?.data) ? (jobsData as any).data :
    Array.isArray(jobsData as any)         ? (jobsData as any) :
    []

  // Backend enums:
  // JobStatus: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  // Incident Status: 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'ESCALATED'
  // Severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  const activeJobs = jobs.filter(
    (job) => job.status === 'PROCESSING' || job.status === 'PENDING'
  )
  const criticalIncidents = incidents.filter(
    (i) => i.severity === 'CRITICAL' && i.status !== 'RESOLVED'
  )

  const hasErrors = Boolean(incidentsError || jobsError || clusterError || healthError)
  const hasTimeouts = Boolean(
    String(incidentsError).includes('timeout') ||
    String(jobsError).includes('timeout') ||
    String(clusterError).includes('timeout') ||
    String(healthError).includes('timeout')
  )
  const isInitialLoading = incidentsLoading && jobsLoading && clusterLoading && healthLoading
  const hasCriticalErrors = hasErrors && !isInitialLoading && !hasTimeouts && (
    // Only show fallback if most queries failed persistently (not timeouts)
    (incidentsError && jobsError && clusterError) || 
    (incidentsError && clusterError && healthError)
  )

  // ─────────────────────────────────────────────────────────────────────────────
  // Actions
  // ─────────────────────────────────────────────────────────────────────────────
  const handleRefreshAll = () => {
    void refetchIncidents()
    void refetchJobs()
    void refetchCluster()
    void refetchHealth()
    toast.success('Dashboard data refreshed')
  }

  const handleCancelJob = async (jobId: string) => {
    try {
      await apiService.cancelJob(jobId)
      void refetchJobs()
      toast.success('Job cancelled successfully')
    } catch {
      toast.error('Failed to cancel job')
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // UI helpers
  // ─────────────────────────────────────────────────────────────────────────────
  const sevColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'text-red-600 bg-red-50'
      case 'HIGH':     return 'text-orange-600 bg-orange-50'
      case 'MEDIUM':   return 'text-yellow-600 bg-yellow-50'
      case 'LOW':      return 'text-blue-600 bg-blue-50'
      default:         return 'text-gray-600 bg-gray-50'
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'OPEN':         return 'text-red-600 bg-red-50'
      case 'IN_PROGRESS':  return 'text-blue-600 bg-blue-50'
      case 'RESOLVED':     return 'text-green-600 bg-green-50'
      case 'ESCALATED':    return 'text-purple-600 bg-purple-50'
      default:             return 'text-gray-600 bg-gray-50'
    }
  }

  const jobStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':  return 'text-green-600 bg-green-50'
      case 'PROCESSING': return 'text-blue-600 bg-blue-50'
      case 'PENDING':    return 'text-yellow-600 bg-yellow-50'
      case 'FAILED':     return 'text-red-600 bg-red-50'
      default:           return 'text-gray-600 bg-gray-50'
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────────
  
  // Show fallback dashboard for critical errors
  if (hasCriticalErrors) {
    return (
      <FallbackDashboard
        onRetry={handleRefreshAll}
        hasTimeouts={hasTimeouts}
        errorMessage={String(incidentsError || jobsError || clusterError || healthError)}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Header + Controls */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600">OneFS Log Intelligence Overview</p>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
              }`}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
              Auto-refresh: {autoRefresh ? 'On' : 'Off'}
            </button>

            <button
              onClick={handleRefreshAll}
              className="flex items-center px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>

        {/* System Health */}
        <div className="flex items-center space-x-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full mr-2 ${
                healthLoading
                  ? 'bg-yellow-400 animate-pulse'
                  : (health as any)?.status === 'healthy'
                  ? 'bg-green-400'
                  : 'bg-red-400'
              }`}
            />
            <span className="text-sm font-medium">
              API:{' '}
              {healthLoading
                ? 'Checking...'
                : (health as any)?.status === 'healthy'
                ? 'Healthy'
                : 'Error'}
            </span>
          </div>

          <div className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full mr-2 ${
                clusterLoading
                  ? 'bg-yellow-400 animate-pulse'
                  : (clusterStatus as any)?.status === 'connected'
                  ? 'bg-green-400'
                  : 'bg-red-400'
              }`}
            />
            <span className="text-sm font-medium">
              Cluster:{' '}
              {clusterLoading ? 'Checking...' : (clusterStatus as any)?.status || 'Unknown'}
            </span>
          </div>

          {(clusterStatus as any)?.cluster && (
            <div className="flex items-center text-sm text-gray-600">
              <Server className="w-4 h-4 mr-1" />
              {(clusterStatus as any).cluster.nodes} nodes •{' '}
              {(clusterStatus as any).cluster.version}
            </div>
          )}
        </div>

        {/* Initial Loading State */}
        {isInitialLoading && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mt-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <RefreshCw className="h-5 w-5 text-blue-400 animate-spin" />
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-blue-800">Loading Dashboard</h3>
                <p className="mt-1 text-sm text-blue-700">
                  Please wait while we load your dashboard data...
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Errors */}
        {hasErrors && !isInitialLoading && (
          <div className={`border rounded-md p-4 mt-4 ${
            hasTimeouts 
              ? 'bg-yellow-50 border-yellow-200' 
              : 'bg-red-50 border-red-200'
          }`}>
            <div className="flex">
              <div className="flex-shrink-0">
                {hasTimeouts ? (
                  <RefreshCw className="h-5 w-5 text-yellow-400 animate-spin" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-400" />
                )}
              </div>
              <div className="ml-3">
                <h3 className={`text-sm font-medium ${
                  hasTimeouts ? 'text-yellow-800' : 'text-red-800'
                }`}>
                  {hasTimeouts ? 'Connection Timeout' : 'Connection Issues'}
                </h3>
                <div className={`mt-2 text-sm ${
                  hasTimeouts ? 'text-yellow-700' : 'text-red-700'
                }`}>
                  <p>
                    {hasTimeouts 
                      ? 'Some dashboard requests timed out. The backend may be slow or unavailable.'
                      : 'Some dashboard data could not be loaded. This can happen if the backend is not running.'
                    }
                  </p>
                  <ul className="list-disc list-inside mt-1 space-y-1">
                    {incidentsError && <li>Incidents: {String(incidentsError)}</li>}
                    {jobsError && <li>Jobs: {String(jobsError)}</li>}
                    {clusterError && <li>Cluster: {String(clusterError)}</li>}
                    {healthError && <li>Health: {String(healthError)}</li>}
                  </ul>
                  {hasTimeouts && (
                    <div className="mt-2">
                      <button
                        onClick={() => setAutoRefresh(false)}
                        className="text-xs font-medium text-yellow-800 underline"
                      >
                        Disable auto-refresh to prevent further timeouts
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Incidents</p>
              <p className="text-2xl font-bold text-gray-900">
                {incidentsLoading ? '…' : incidents.length}
              </p>
            </div>
            <div className="p-3 bg-blue-50 rounded-full">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Critical Incidents</p>
              <p className="text-2xl font-bold text-red-600">
                {incidentsLoading ? '…' : criticalIncidents.length}
              </p>
            </div>
            <div className="p-3 bg-red-50 rounded-full">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active Jobs</p>
              <p className="text-2xl font-bold text-gray-900">
                {jobsLoading ? '…' : activeJobs.length}
              </p>
            </div>
            <div className="p-3 bg-green-50 rounded-full">
              <Activity className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Completed Jobs</p>
              <p className="text-2xl font-bold text-green-600">
                {jobsLoading ? '…' : jobs.filter((j) => j.status === 'COMPLETED').length}
              </p>
            </div>
            <div className="p-3 bg-green-50 rounded-full">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Incidents */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Incidents</h2>

          {incidentsLoading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded" />
              <div className="h-4 bg-gray-200 rounded w-5/6" />
              <div className="h-4 bg-gray-200 rounded w-4/6" />
            </div>
          ) : incidents.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No incidents found</p>
          ) : (
            <div className="space-y-3">
              {incidents.slice(0, 5).map((incident: any) => (
                <div key={incident.id} className="border-l-4 border-gray-200 pl-4 py-2">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-gray-900">{incident.title}</h3>
                      <div className="flex items-center space-x-2 mt-1">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${sevColor(
                            incident.severity
                          )}`}
                        >
                          {incident.severity}
                        </span>
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${statusColor(
                            incident.status
                          )}`}
                        >
                          {incident.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {new Date(incident.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Active Jobs */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Active Jobs</h2>
          {jobsLoading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded" />
              <div className="h-4 bg-gray-200 rounded w-5/6" />
              <div className="h-4 bg-gray-200 rounded w-4/6" />
            </div>
          ) : activeJobs.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No active jobs</p>
          ) : (
            <div className="space-y-3">
              {activeJobs.slice(0, 5).map((job: any) => (
                <div key={job.id} className="border-l-4 border-blue-200 pl-4 py-2">
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-gray-900">{job.filename}</h3>
                      <div className="flex items-center space-x-2 mt-1">
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${jobStatusColor(job.status)}`}>
                          {job.status}
                        </span>
                        {job.progress > 0 && (
                          <div className="flex items-center">
                            <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                              <div 
                                className="bg-blue-600 h-2 rounded-full" 
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-500">{job.progress}%</span>
                          </div>
                        )}
                      </div>
                    </div>
                    {job.status === 'PROCESSING' && (
                      <button
                        onClick={() => handleCancelJob(job.id)}
                        className="ml-2 text-red-600 hover:text-red-800"
                        title="Cancel job"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={() => navigate('/ingest')}
            className="flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            <Upload className="w-5 h-5 mr-2" />
            Upload Log File
          </button>
          <Link 
            to="/incidents"
            className="flex items-center justify-center px-4 py-3 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
          >
            <FileText className="w-5 h-5 mr-2" />
            View All Incidents
          </Link>
          <Link 
            to="/jobs"
            className="flex items-center justify-center px-4 py-3 bg-gray-600 text-white rounded-md hover:bg-gray-700 transition-colors"
          >
            <Activity className="w-5 h-5 mr-2" />
            View All Jobs
          </Link>
        </div>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiService } from '@/services/api'
import {
  AlertTriangle,
  RefreshCw,
  Search,
  XCircle,
  Server,
  Calendar,
  Tag,
  LayoutDashboard,
  List,
  ArrowUpCircle,
  History,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import toast from 'react-hot-toast'
import { WorkDetailsModal } from '@/components/WorkDetailsModal'
import { EscalateModal } from '@/components/EscalateModal'
import { RawLog } from '@/components/RawLog'
import { ActivityTimeline } from '@/components/ActivityTimeline'
import { Summary, Escalation } from '@/types'

export function Incidents() {
  const [filters, setFilters] = useState({
    severity: '',
    status: '',
    limit: 50,
    skip: 0
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [showWorkModal, setShowWorkModal] = useState(false)
  const [showEscalateModal, setShowEscalateModal] = useState(false)
  const [selectedIncident, setSelectedIncident] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'dashboard' | 'list' | 'escalations'>('dashboard')
  const [expandedActivity, setExpandedActivity] = useState<number | null>(null)

  const queryClient = useQueryClient()

  const {
    data: incidentsData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => apiService.getIncidents(filters),
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 1000 * 60 * 2,
  })

  const { data: summaryData } = useQuery<Summary>({
    queryKey: ['summary', 24],
    queryFn: () => apiService.getSummary(24),
    refetchInterval: 60_000,
    retry: 1,
  })

  const { data: escalationsData } = useQuery<{ escalations: Escalation[] }>({
    queryKey: ['escalations'],
    queryFn: () => apiService.getEscalations(),
    refetchInterval: 60_000,
    retry: 1,
  })

  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => 
      apiService.updateIncidentStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      toast.success('Incident status updated')
      setShowWorkModal(false)
      setShowEscalateModal(false)
      setSelectedIncident(null)
    },
    onError: () => {
      toast.error('Failed to update incident status')
    }
  })

  const incidents = incidentsData?.incidents || []
  const total = incidentsData?.total || 0

  const filteredIncidents = incidents.filter((incident: any) =>
    incident.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    incident.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    incident.node?.hostname?.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleStartWork = (incident: any) => {
    setSelectedIncident(incident)
    setShowWorkModal(true)
  }

  const handleEscalate = (incident: any) => {
    setSelectedIncident(incident)
    setShowEscalateModal(true)
  }

  const handleWorkSubmit = () => {
    updateStatusMutation.mutate({
      id: selectedIncident.id,
      status: 'IN_PROGRESS'
    })
  }

  const handleEscalateSubmit = () => {
    updateStatusMutation.mutate({
      id: selectedIncident.id,
      status: 'ESCALATED'
    })
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value, skip: 0 }))
  }

  const sevColor = (severity: string) => {
    switch (severity) {
      case 'CRITICAL': return 'text-red-600 bg-red-50 border-red-200'
      case 'HIGH': return 'text-orange-600 bg-orange-50 border-orange-200'
      case 'MEDIUM': return 'text-yellow-600 bg-yellow-50 border-yellow-200'
      case 'LOW': return 'text-blue-600 bg-blue-50 border-blue-200'
      default: return 'text-gray-600 bg-gray-50 border-gray-200'
    }
  }

  const statusColor = (status: string) => {
    switch (status) {
      case 'OPEN': return 'text-red-600 bg-red-50'
      case 'IN_PROGRESS': return 'text-blue-600 bg-blue-50'
      case 'RESOLVED': return 'text-green-600 bg-green-50'
      case 'ESCALATED': return 'text-purple-600 bg-purple-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  const getSeverityTotal = (severity: string) => {
    if (!summaryData?.summary?.[severity]) return 0
    return Object.values(summaryData.summary[severity]).reduce((a, b) => a + b, 0)
  }

  const getStatusCount = (severity: string, status: string) => {
    return summaryData?.summary?.[severity]?.[status] || 0
  }

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Incidents</h1>
            <p className="text-gray-600">{total} total incident{total !== 1 ? 's' : ''}</p>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
        </div>

        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search incidents..."
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
            <select
              value={filters.severity}
              onChange={(e) => handleFilterChange('severity', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="RESOLVED">Resolved</option>
              <option value="ESCALATED">Escalated</option>
            </select>
          </div>
        </div>

        <div className="flex space-x-1 mt-6 border-b border-gray-200">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
              activeTab === 'dashboard'
                ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            <LayoutDashboard className="w-4 h-4 mr-2" />
            Dashboard
          </button>
          <button
            onClick={() => setActiveTab('list')}
            className={`flex items-center px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
              activeTab === 'list'
                ? 'bg-blue-50 text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            <List className="w-4 h-4 mr-2" />
            List View
          </button>
          <button
            onClick={() => setActiveTab('escalations')}
            className={`flex items-center px-4 py-2 font-medium text-sm rounded-t-lg transition-colors ${
              activeTab === 'escalations'
                ? 'bg-purple-50 text-purple-600 border-b-2 border-purple-600'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
            }`}
          >
            <ArrowUpCircle className="w-4 h-4 mr-2" />
            Escalations
            {escalationsData?.escalations && escalationsData.escalations.length > 0 && (
              <span className="ml-2 bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full text-xs">
                {escalationsData.escalations.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <XCircle className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error Loading Incidents</h3>
              <p className="mt-1 text-sm text-red-700">{String(error)}</p>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((severity) => (
              <div key={severity} className={`p-4 rounded-lg border-2 ${sevColor(severity)}`}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-bold text-lg">{severity}</h3>
                  <span className="text-2xl font-bold">{getSeverityTotal(severity)}</span>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between"><span>Open:</span><span className="font-medium">{getStatusCount(severity, 'OPEN')}</span></div>
                  <div className="flex justify-between"><span>In Progress:</span><span className="font-medium">{getStatusCount(severity, 'IN_PROGRESS')}</span></div>
                  <div className="flex justify-between"><span>Resolved:</span><span className="font-medium">{getStatusCount(severity, 'RESOLVED')}</span></div>
                  <div className="flex justify-between"><span>Escalated:</span><span className="font-medium">{getStatusCount(severity, 'ESCALATED')}</span></div>
                </div>
              </div>
            ))}
          </div>

          {escalationsData?.escalations && escalationsData.escalations.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-gray-900 flex items-center">
                  <ArrowUpCircle className="w-5 h-5 mr-2 text-purple-600" />
                  Recent Escalations
                </h3>
                <button onClick={() => setActiveTab('escalations')} className="text-sm text-purple-600 hover:text-purple-800">View All</button>
              </div>
              <div className="space-y-3">
                {escalationsData.escalations.slice(0, 5).map((escalation: Escalation) => (
                  <div key={escalation.id} className="flex items-start justify-between p-3 bg-purple-50 rounded-lg">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900">{escalation.title}</p>
                      <div className="flex items-center space-x-3 text-sm text-gray-500 mt-1">
                        <span className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${sevColor(escalation.severity)}`}>{escalation.severity}</span>
                        {escalation.node && <span className="flex items-center"><Server className="w-3 h-3 mr-1" />{escalation.node}</span>}
                        <span>{new Date(escalation.created_at).toLocaleString()}</span>
                      </div>
                      {(escalation as any).raw_log && (
                        <div className="mt-2">
                          <RawLog log={(escalation as any).raw_log} maxLength={80} />
                        </div>
                      )}
                    </div>
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${statusColor(escalation.status)}`}>{escalation.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'list' && (
        <div className="bg-white rounded-lg shadow">
          {isLoading ? (
            <div className="p-6 space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
                  <div className="h-3 bg-gray-200 rounded w-1/2 mb-2" />
                  <div className="h-3 bg-gray-200 rounded w-1/4" />
                </div>
              ))}
            </div>
          ) : filteredIncidents.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>No incidents found</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredIncidents.map((incident: any) => (
                <div key={incident.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-lg font-medium text-gray-900">{incident.title}</h3>
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${sevColor(incident.severity)}`}>{incident.severity}</span>
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${statusColor(incident.status)}`}>{incident.status}</span>
                      </div>
                      <p className="text-gray-600 mb-3">{incident.description}</p>
                      {incident.raw_log && (
                        <div className="mb-3">
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Matched Log:</span>
                          <RawLog log={incident.raw_log} className="mt-1" />
                        </div>
                      )}
                      <div className="flex items-center space-x-6 text-sm text-gray-500">
                        {incident.node && <div className="flex items-center"><Server className="w-4 h-4 mr-1" />{incident.node.hostname}</div>}
                        {incident.pattern && <div className="flex items-center"><Tag className="w-4 h-4 mr-1" />{incident.pattern.name}</div>}
                        <div className="flex items-center"><Calendar className="w-4 h-4 mr-1" />{new Date(incident.created_at).toLocaleString()}</div>
                      </div>
                      {/* Activity History Toggle */}
                      <div className="mt-4 pt-3 border-t border-gray-100">
                        <button
                          onClick={() => setExpandedActivity(expandedActivity === incident.id ? null : incident.id)}
                          className="flex items-center text-sm text-gray-600 hover:text-gray-900"
                        >
                          <History className="w-4 h-4 mr-2" />
                          Activity History
                          {expandedActivity === incident.id ? (
                            <ChevronUp className="w-4 h-4 ml-2" />
                          ) : (
                            <ChevronDown className="w-4 h-4 ml-2" />
                          )}
                        </button>
                        {expandedActivity === incident.id && (
                          <div className="mt-3">
                            <ActivityTimeline incidentId={incident.id} />
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      {incident.status === 'OPEN' && (
                        <>
                          <button onClick={() => handleStartWork(incident)} className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors">Start Work</button>
                          <button onClick={() => handleEscalate(incident)} className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors">Escalate</button>
                        </>
                      )}
                      {incident.status === 'IN_PROGRESS' && (
                        <button onClick={() => updateStatusMutation.mutate({ id: incident.id, status: 'RESOLVED' })} className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors">Resolve</button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'escalations' && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h3 className="text-lg font-bold text-gray-900 flex items-center">
              <ArrowUpCircle className="w-5 h-5 mr-2 text-purple-600" />
              All Escalations
            </h3>
            <p className="text-gray-600 mt-1">High-priority incidents requiring immediate attention</p>
          </div>
          {escalationsData?.escalations && escalationsData.escalations.length === 0 ? (
            <div className="p-6 text-center text-gray-500">
              <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>No escalations found</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {escalationsData?.escalations?.map((escalation: Escalation) => (
                <div key={escalation.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-lg font-medium text-gray-900">{escalation.title}</h3>
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${sevColor(escalation.severity)}`}>{escalation.severity}</span>
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${statusColor(escalation.status)}`}>{escalation.status}</span>
                      </div>
                      <div className="flex items-center space-x-4 text-sm text-gray-500">
                        {escalation.node && <div className="flex items-center"><Server className="w-4 h-4 mr-1" />{escalation.node}</div>}
                        <div className="flex items-center"><Calendar className="w-4 h-4 mr-1" />{new Date(escalation.created_at).toLocaleString()}</div>
                      </div>
                      {(escalation as any).raw_log && (
                        <div className="mt-3">
                          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Matched Log:</span>
                          <RawLog log={(escalation as any).raw_log} className="mt-1" />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <WorkDetailsModal isOpen={showWorkModal} onClose={() => setShowWorkModal(false)} onSubmit={handleWorkSubmit} incidentTitle={selectedIncident?.title || ''} />
      <EscalateModal isOpen={showEscalateModal} onClose={() => setShowEscalateModal(false)} onSubmit={handleEscalateSubmit} incidentTitle={selectedIncident?.title || ''} />
    </div>
  )
}
       

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Plus,
  Edit2,
  Trash2,
  Server,
  Filter,
  Activity,
  AlertCircle,
  Calendar,
  ChevronDown,
  ChevronUp,
  X,
  ExternalLink,
  MapPin,
  Tag
} from 'lucide-react'
import { apiService } from '@/services/api'
import { Node } from '@/types'
import { StatusBadge } from '@/components/StatusBadge'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'

const nodeTypeColors: Record<string, string> = {
  onefs: 'bg-blue-100 text-blue-800',
  linux: 'bg-green-100 text-green-800',
  vmware: 'bg-purple-100 text-purple-800',
  unknown: 'bg-gray-100 text-gray-800',
}

export function Nodes() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showIncidentsModal, setShowIncidentsModal] = useState(false)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [expandedNode, setExpandedNode] = useState<number | null>(null)

  // Form states
  const [formData, setFormData] = useState({
    hostname: '',
    ip_address: '',
    node_type: 'unknown',
    version: '',
    description: '',
  })

  // Fetch nodes
  const { data: nodes, isLoading } = useQuery({
    queryKey: ['nodes', typeFilter],
    queryFn: () =>
      apiService.getNodes({
        node_type: typeFilter || undefined,
      }),
  })

  // Fetch node types
  const { data: nodeTypes } = useQuery({
    queryKey: ['node-types'],
    queryFn: () => apiService.getNodeTypes(),
  })

  // Fetch node incidents when viewing
  const { data: nodeIncidentsData, isLoading: incidentsLoading } = useQuery({
    queryKey: ['node-incidents', selectedNode?.id],
    queryFn: () =>
      selectedNode ? apiService.getNodeIncidents(selectedNode.id) : null,
    enabled: !!selectedNode && showIncidentsModal,
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => apiService.createNode(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nodes'] })
      toast.success('Node created successfully')
      setShowCreateModal(false)
      setFormData({
        hostname: '',
        ip_address: '',
        node_type: 'unknown',
        version: '',
        description: '',
      })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create node')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Node> }) =>
      apiService.updateNode(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nodes'] })
      toast.success('Node updated successfully')
      setShowEditModal(false)
      setSelectedNode(null)
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update node')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiService.deleteNode(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nodes'] })
      toast.success('Node deleted successfully')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete node')
    },
  })

  // Filter nodes by search
  const filteredNodes = useMemo(() => {
    if (!nodes) return []
    if (!searchQuery) return nodes
    return nodes.filter(
      (n) =>
        n.hostname.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.ip_address?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.description?.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [nodes, searchQuery])

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleEdit = (node: Node) => {
    setSelectedNode(node)
    setFormData({
      hostname: node.hostname,
      ip_address: node.ip_address || '',
      node_type: node.node_type || 'unknown',
      version: node.version || '',
      description: node.description || '',
    })
    setShowEditModal(true)
  }

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedNode) {
      updateMutation.mutate({ id: selectedNode.id, data: formData })
    }
  }

  const handleViewIncidents = (node: Node) => {
    setSelectedNode(node)
    setShowIncidentsModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Node Management</h1>
          <p className="text-gray-500 mt-1">
            Manage discovered nodes and view their incident history
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Node
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Nodes</p>
              <p className="text-2xl font-bold text-gray-900">{nodes?.length || 0}</p>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <Server className="w-5 h-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">OneFS Nodes</p>
              <p className="text-2xl font-bold text-blue-600">
                {nodes?.filter((n) => n.node_type === 'onefs').length || 0}
              </p>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <Server className="w-5 h-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">With Incidents</p>
              <p className="text-2xl font-bold text-orange-600">
                {nodes?.filter((n) => (n.incident_count || 0) > 0).length || 0}
              </p>
            </div>
            <div className="p-3 bg-orange-50 rounded-lg">
              <AlertCircle className="w-5 h-5 text-orange-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Incidents</p>
              <p className="text-2xl font-bold text-purple-600">
                {nodes?.reduce((sum, n) => sum + (n.incident_count || 0), 0) || 0}
              </p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg">
              <Activity className="w-5 h-5 text-purple-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
              <input
                type="text"
                placeholder="Search nodes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Types</option>
              {nodeTypes?.map((type) => (
                <option key={type} value={type}>
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Nodes List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
            <p className="mt-2 text-gray-500">Loading nodes...</p>
          </div>
        ) : filteredNodes?.length === 0 ? (
          <div className="p-8 text-center">
            <Server className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No nodes found</p>
            <p className="text-sm text-gray-400 mt-1">
              Nodes are automatically created when logs are ingested
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredNodes?.map((node) => (
              <div key={node.id} className="p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3">
                      <h3 className="text-lg font-medium text-gray-900">{node.hostname}</h3>
                      {node.node_type && (
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                            nodeTypeColors[node.node_type] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {node.node_type}
                        </span>
                      )}
                      {(node.incident_count || 0) > 0 && (
                        <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full bg-orange-100 text-orange-800">
                          <AlertCircle className="w-3 h-3 mr-1" />
                          {node.incident_count} incidents
                        </span>
                      )}
                    </div>
                    <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                      {node.ip_address && (
                        <span className="flex items-center">
                          <MapPin className="w-4 h-4 mr-1" />
                          {node.ip_address}
                        </span>
                      )}
                      {node.version && (
                        <span className="flex items-center">
                          <Tag className="w-4 h-4 mr-1" />
                          {node.version}
                        </span>
                      )}
                      <span className="flex items-center">
                        <Calendar className="w-4 h-4 mr-1" />
                        Discovered {new Date(node.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    {node.description && (
                      <p className="text-gray-600 mt-2">{node.description}</p>
                    )}
                  </div>
                  <div className="flex items-center space-x-2 ml-4">
                    {(node.incident_count || 0) > 0 && (
                      <button
                        onClick={() => handleViewIncidents(node)}
                        className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                        title="View incidents"
                      >
                        <Activity className="w-4 h-4" />
                      </button>
                    )}
                    <Link
                      to={`/incidents?node_id=${node.id}`}
                      className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Filter incidents"
                    >
                      <Filter className="w-4 h-4" />
                    </Link>
                    <button
                      onClick={() => handleEdit(node)}
                      className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Edit node"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(node.id)}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                      title="Delete node"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() =>
                        setExpandedNode(expandedNode === node.id ? null : node.id)
                      }
                      className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      {expandedNode === node.id ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                {expandedNode === node.id && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-gray-500">Node ID</p>
                        <p className="font-medium">{node.id}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Type</p>
                        <p className="font-medium capitalize">{node.node_type || 'Unknown'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Version</p>
                        <p className="font-medium">{node.version || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Last Updated</p>
                        <p className="font-medium">
                          {node.updated_at
                            ? new Date(node.updated_at).toLocaleDateString()
                            : 'Never'}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || showEditModal) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">
                {showEditModal ? 'Edit Node' : 'Add Node'}
              </h2>
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(false)
                  setSelectedNode(null)
                }}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={showEditModal ? handleUpdate : handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Hostname</label>
                <input
                  type="text"
                  required
                  value={formData.hostname}
                  onChange={(e) => setFormData({ ...formData, hostname: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Test-9700-1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">IP Address</label>
                <input
                  type="text"
                  value={formData.ip_address}
                  onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., 203.0.113.10"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                  <select
                    value={formData.node_type}
                    onChange={(e) => setFormData({ ...formData, node_type: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="onefs">OneFS</option>
                    <option value="linux">Linux</option>
                    <option value="vmware">VMware</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Version</label>
                  <input
                    type="text"
                    value={formData.version}
                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., 9.5.0.0"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows={2}
                  placeholder="Optional description"
                />
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    setShowEditModal(false)
                    setSelectedNode(null)
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  {showEditModal ? 'Update Node' : 'Add Node'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Incidents Modal */}
      {showIncidentsModal && selectedNode && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] overflow-hidden">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-900">Incidents for {selectedNode.hostname}</h2>
                <p className="text-sm text-gray-500">
                  {nodeIncidentsData?.total || 0} total incidents
                </p>
              </div>
              <button
                onClick={() => {
                  setShowIncidentsModal(false)
                  setSelectedNode(null)
                }}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="overflow-y-auto max-h-[60vh] p-6">
              {incidentsLoading ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
                  <p className="mt-2 text-gray-500">Loading incidents...</p>
                </div>
              ) : nodeIncidentsData?.incidents.length === 0 ? (
                <div className="text-center py-8">
                  <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500">No incidents found</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {nodeIncidentsData?.incidents.map((incident) => (
                    <div
                      key={incident.id}
                      className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-medium text-gray-900">{incident.title}</h3>
                          <p className="text-sm text-gray-600 mt-1">{incident.description}</p>
                          <div className="flex items-center space-x-3 mt-2 text-sm">
                            <StatusBadge status={incident.severity} />
                            <StatusBadge status={incident.status} />
                            {incident.pattern && (
                              <span className="text-gray-500">Pattern: {incident.pattern}</span>
                            )}
                            <span className="text-gray-400">
                              {new Date(incident.created_at).toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <Link
                          to={`/incidents?incident_id=${incident.id}`}
                          className="p-2 text-gray-400 hover:text-blue-600"
                          onClick={() => setShowIncidentsModal(false)}
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <div className="flex justify-end">
                <Link
                  to={`/incidents?node_id=${selectedNode.id}`}
                  className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  onClick={() => setShowIncidentsModal(false)}
                >
                  View All Incidents
                  <ExternalLink className="w-4 h-4 ml-2" />
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

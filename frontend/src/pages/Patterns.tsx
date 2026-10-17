import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Plus,
  Edit2,
  Trash2,
  Play,
  CheckCircle,
  XCircle,
  Filter,
  Code,
  Tag,
  Activity,
  ChevronDown,
  ChevronUp,
  X
} from 'lucide-react'
import { apiService } from '@/services/api'
import { Pattern } from '@/types'
import { StatusBadge } from '@/components/StatusBadge'
import toast from 'react-hot-toast'

const severityColors: Record<string, string> = {
  CRITICAL: 'bg-red-100 text-red-800',
  HIGH: 'bg-orange-100 text-orange-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  LOW: 'bg-blue-100 text-blue-800',
}

const categoryColors: Record<string, string> = {
  system: 'bg-purple-100 text-purple-800',
  hardware: 'bg-red-100 text-red-800',
  network: 'bg-blue-100 text-blue-800',
  security: 'bg-orange-100 text-orange-800',
  storage: 'bg-green-100 text-green-800',
  custom: 'bg-gray-100 text-gray-800',
}

export function Patterns() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showTestModal, setShowTestModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedPattern, setSelectedPattern] = useState<Pattern | null>(null)
  const [expandedPattern, setExpandedPattern] = useState<number | null>(null)

  // Form states
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    regex_pattern: '',
    category: 'custom',
    severity_level: 'MEDIUM',
  })
  const [testLine, setTestLine] = useState('')
  const [testResult, setTestResult] = useState<{
    matches: boolean
    matched_text?: string
    groups: string[]
  } | null>(null)

  // Fetch patterns
  const { data: patterns, isLoading } = useQuery({
    queryKey: ['patterns', categoryFilter, severityFilter, statusFilter],
    queryFn: () =>
      apiService.getPatterns({
        category: categoryFilter || undefined,
        severity: severityFilter || undefined,
        is_active: statusFilter === 'active' ? true : statusFilter === 'inactive' ? false : undefined,
      }),
  })

  // Fetch categories
  const { data: categories } = useQuery({
    queryKey: ['pattern-categories'],
    queryFn: () => apiService.getPatternCategories(),
  })

  // Mutations
  const toggleMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: number; isActive: boolean }) =>
      apiService.togglePattern(id, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patterns'] })
      toast.success('Pattern status updated')
    },
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof formData) => apiService.createPattern(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patterns'] })
      toast.success('Pattern created successfully')
      setShowCreateModal(false)
      setFormData({
        name: '',
        description: '',
        regex_pattern: '',
        category: 'custom',
        severity_level: 'MEDIUM',
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Pattern> }) =>
      apiService.updatePattern(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patterns'] })
      toast.success('Pattern updated successfully')
      setShowEditModal(false)
      setSelectedPattern(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiService.deletePattern(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patterns'] })
      toast.success('Pattern deleted successfully')
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete pattern')
    },
  })

  const testMutation = useMutation({
    mutationFn: ({ regex, line }: { regex: string; line: string }) =>
      apiService.testPattern(regex, line),
    onSuccess: (data) => {
      setTestResult(data)
    },
  })

  // Filter patterns by search
  const filteredPatterns = useMemo(() => {
    if (!patterns) return []
    if (!searchQuery) return patterns
    return patterns.filter(
      (p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.regex_pattern.toLowerCase().includes(searchQuery.toLowerCase())
    )
  }, [patterns, searchQuery])

  const handleToggle = (pattern: Pattern) => {
    toggleMutation.mutate({ id: pattern.id, isActive: !pattern.is_active })
  }

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate(formData)
  }

  const handleEdit = (pattern: Pattern) => {
    setSelectedPattern(pattern)
    setFormData({
      name: pattern.name,
      description: pattern.description || '',
      regex_pattern: pattern.regex_pattern,
      category: pattern.category || 'custom',
      severity_level: pattern.severity_level,
    })
    setShowEditModal(true)
  }

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedPattern) {
      updateMutation.mutate({ id: selectedPattern.id, data: formData })
    }
  }

  const handleTest = (e: React.FormEvent) => {
    e.preventDefault()
    testMutation.mutate({ regex: formData.regex_pattern, line: testLine })
  }

  const openTestModal = (pattern?: Pattern) => {
    if (pattern) {
      setFormData({
        name: pattern.name,
        description: pattern.description || '',
        regex_pattern: pattern.regex_pattern,
        category: pattern.category || 'custom',
        severity_level: pattern.severity_level,
      })
    } else {
      setFormData({
        name: '',
        description: '',
        regex_pattern: '',
        category: 'custom',
        severity_level: 'MEDIUM',
      })
    }
    setTestLine('')
    setTestResult(null)
    setShowTestModal(true)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pattern Management</h1>
          <p className="text-gray-500 mt-1">
            Manage log detection patterns for OneFS and custom log sources
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => openTestModal()}
            className="inline-flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <Play className="w-4 h-4 mr-2" />
            Test Pattern
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Pattern
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Patterns</p>
              <p className="text-2xl font-bold text-gray-900">{patterns?.length || 0}</p>
            </div>
            <div className="p-3 bg-blue-50 rounded-lg">
              <Code className="w-5 h-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Active</p>
              <p className="text-2xl font-bold text-green-600">
                {patterns?.filter((p) => p.is_active).length || 0}
              </p>
            </div>
            <div className="p-3 bg-green-50 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Inactive</p>
              <p className="text-2xl font-bold text-gray-600">
                {patterns?.filter((p) => !p.is_active).length || 0}
              </p>
            </div>
            <div className="p-3 bg-gray-100 rounded-lg">
              <XCircle className="w-5 h-5 text-gray-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Categories</p>
              <p className="text-2xl font-bold text-purple-600">
                {categories?.length || 0}
              </p>
            </div>
            <div className="p-3 bg-purple-50 rounded-lg">
              <Tag className="w-5 h-5 text-purple-600" />
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
                placeholder="Search patterns..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Categories</option>
              {categories?.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </option>
              ))}
            </select>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>
      </div>

      {/* Patterns List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto" />
            <p className="mt-2 text-gray-500">Loading patterns...</p>
          </div>
        ) : filteredPatterns?.length === 0 ? (
          <div className="p-8 text-center">
            <Code className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No patterns found</p>
            <p className="text-sm text-gray-400 mt-1">
              Try adjusting your filters or create a new pattern
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {filteredPatterns?.map((pattern) => (
              <div key={pattern.id} className="p-4 hover:bg-gray-50 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-3">
                      <h3 className="text-lg font-medium text-gray-900">{pattern.name}</h3>
                      <span
                        className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                          severityColors[pattern.severity_level] || 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {pattern.severity_level}
                      </span>
                      {pattern.category && (
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${
                            categoryColors[pattern.category] || 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          {pattern.category}
                        </span>
                      )}
                      <StatusBadge status={pattern.is_active ? 'Active' : 'Inactive'} />
                    </div>
                    <p className="text-gray-600 mt-1">{pattern.description}</p>
                    <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                      <span className="flex items-center">
                        <Activity className="w-4 h-4 mr-1" />
                        {pattern.incident_count || 0} incidents
                      </span>
                      <span>Created {new Date(pattern.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={() => openTestModal(pattern)}
                      className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Test pattern"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleToggle(pattern)}
                      className={`p-2 transition-colors ${
                        pattern.is_active
                          ? 'text-green-500 hover:text-green-700'
                          : 'text-gray-400 hover:text-gray-600'
                      }`}
                      title={pattern.is_active ? 'Disable pattern' : 'Enable pattern'}
                    >
                      {pattern.is_active ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : (
                        <XCircle className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => handleEdit(pattern)}
                      className="p-2 text-gray-400 hover:text-blue-600 transition-colors"
                      title="Edit pattern"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate(pattern.id)}
                      className="p-2 text-gray-400 hover:text-red-600 transition-colors"
                      title="Delete pattern"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() =>
                        setExpandedPattern(expandedPattern === pattern.id ? null : pattern.id)
                      }
                      className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      {expandedPattern === pattern.id ? (
                        <ChevronUp className="w-4 h-4" />
                      ) : (
                        <ChevronDown className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
                {expandedPattern === pattern.id && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                        Regex Pattern
                      </p>
                      <code className="text-sm font-mono text-gray-700 break-all">
                        {pattern.regex_pattern}
                      </code>
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
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">
                {showEditModal ? 'Edit Pattern' : 'Create New Pattern'}
              </h2>
              <button
                onClick={() => {
                  setShowCreateModal(false)
                  setShowEditModal(false)
                  setSelectedPattern(null)
                }}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={showEditModal ? handleUpdate : handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., OneFS Authentication Failure"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows={2}
                  placeholder="Brief description of what this pattern detects"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Regex Pattern
                </label>
                <textarea
                  required
                  value={formData.regex_pattern}
                  onChange={(e) => setFormData({ ...formData, regex_pattern: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={3}
                  placeholder="e.g., error.*PAM.*Authentication|authentication.*fail"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Use Python regex syntax. Test your pattern before saving.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="system">System</option>
                    <option value="hardware">Hardware</option>
                    <option value="network">Network</option>
                    <option value="security">Security</option>
                    <option value="storage">Storage</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
                  <select
                    value={formData.severity_level}
                    onChange={(e) =>
                      setFormData({ ...formData, severity_level: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="LOW">Low</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    setShowEditModal(false)
                    setSelectedPattern(null)
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    setShowEditModal(false)
                    setShowTestModal(true)
                  }}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                >
                  Test First
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  {showEditModal ? 'Update Pattern' : 'Create Pattern'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Test Modal */}
      {showTestModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
            <div className="p-6 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-xl font-bold text-gray-900">Test Pattern</h2>
              <button
                onClick={() => {
                  setShowTestModal(false)
                  setTestResult(null)
                }}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleTest} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Regex Pattern
                </label>
                <textarea
                  required
                  value={formData.regex_pattern}
                  onChange={(e) => setFormData({ ...formData, regex_pattern: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={3}
                  placeholder="Enter regex pattern to test"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Test Log Line
                </label>
                <textarea
                  required
                  value={testLine}
                  onChange={(e) => setTestLine(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  rows={3}
                  placeholder="Enter a log line to test against the pattern"
                />
              </div>
              <button
                type="submit"
                disabled={testMutation.isPending}
                className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {testMutation.isPending ? 'Testing...' : 'Run Test'}
              </button>
              {testResult && (
                <div
                  className={`p-4 rounded-lg ${
                    testResult.matches ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    {testResult.matches ? (
                      <>
                        <CheckCircle className="w-5 h-5 text-green-600" />
                        <span className="font-medium text-green-800">Pattern matched!</span>
                      </>
                    ) : (
                      <>
                        <XCircle className="w-5 h-5 text-red-600" />
                        <span className="font-medium text-red-800">No match found</span>
                      </>
                    )}
                  </div>
                  {testResult.matches && testResult.matched_text && (
                    <div className="mt-3">
                      <p className="text-sm font-medium text-gray-700">Matched text:</p>
                      <code className="text-sm font-mono text-green-700 bg-green-100 px-2 py-1 rounded mt-1 inline-block">
                        {testResult.matched_text}
                      </code>
                    </div>
                  )}
                  {testResult.groups && testResult.groups.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-medium text-gray-700">Captured groups:</p>
                      <ul className="mt-1 space-y-1">
                        {testResult.groups.map((group, idx) => (
                          <li key={idx} className="text-sm font-mono text-gray-600">
                            Group {idx + 1}: {group}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              <div className="flex justify-end pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowTestModal(false)
                    setTestResult(null)
                  }}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

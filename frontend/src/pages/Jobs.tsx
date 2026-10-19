import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { apiService } from '@/services/api'
import {
  RefreshCw,
  Upload,
  Eye,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  Play,
  Clock,
  FileText,
  Server
} from 'lucide-react'
import toast from 'react-hot-toast'
import { Job } from '@/types'
import { StatusBadge } from '@/components/StatusBadge'
import { ProgressBar } from '@/components/ProgressBar'
import { SearchInput } from '@/components/SearchInput'
import { EmptyState } from '@/components/EmptyState'
import { ClusterPicker } from '@/components/ClusterPicker'
import { CancelJobButton } from '@/components/CancelJobButton'
import { useClusters } from '@/hooks/useClusters'
import { useJobEvents } from '@/hooks/useJobEvents'
import { FileUpload, FilePreview } from '@/components/FileUpload'

export function Jobs() {
  console.log('Jobs component - rendering')
  
  const [filters, setFilters] = useState({
    status: '',
    cluster: '',
    limit: 20,
    skip: 0
  })
  const [searchTerm, setSearchTerm] = useState('')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [selectedJob, setSelectedJob] = useState<Job | null>(null)
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [expandedJobs, setExpandedJobs] = useState<Set<string>>(new Set())
  const [sseJobId, setSseJobId] = useState<string | null>(null)

  const queryClient = useQueryClient()
  const { clusters } = useClusters()

  // SSE real-time updates for active job
  const { isConnected: sseConnected } = useJobEvents(sseJobId, {
    onProgress: (event) => {
      console.log('Job progress:', event.progress, '%')
      // Refresh jobs list when progress updates
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onComplete: (event) => {
      console.log('Job completed:', event.id)
      toast.success(`Job completed with ${event.result_summary?.incidents_created || 0} incidents`)
      setSseJobId(null)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error) => {
      console.error('SSE error:', error)
      setSseJobId(null)
    }
  })

  // Data fetching
  const {
    data: jobsData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['jobs', filters],
    queryFn: () => apiService.getJobs(filters),
    refetchInterval: 5_000, // 5 second polling for real-time updates
    retry: 1,
    staleTime: 1000 * 60 * 2,
  })

  // Job cancellation is owned by <CancelJobButton/> (confirm-then-cancel
  // with honest 404/409/422/503 states) — no local mutation needed.

  // Normalize jobs data - handle different response structures
  const jobs: Job[] = (() => {
    const jobsArray = jobsData?.jobs || jobsData?.data || jobsData
    if (Array.isArray(jobsArray)) {
      // Handle case where it might be a 2D array
      const flattened = Array.isArray(jobsArray[0]) ? jobsArray.flat() : jobsArray
      return flattened as Job[]
    }
    return []
  })()

  // Filter by search term
  const filteredJobs = jobs.filter((job: Job) =>
    job.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.id.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleViewDetails = (job: Job) => {
    setSelectedJob(job)
    setShowDetailsModal(true)
  }

  const toggleJobExpansion = (jobId: string) => {
    const newExpanded = new Set(expandedJobs)
    if (newExpanded.has(jobId)) {
      newExpanded.delete(jobId)
    } else {
      newExpanded.add(jobId)
    }
    setExpandedJobs(newExpanded)
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A'
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  // Parse result_summary to get incident count
  const getIncidentCount = (job: Job): number => {
    if (!job.result_summary) return 0
    try {
      const summary = JSON.parse(job.result_summary)
      return summary.incidents_created || 0
    } catch {
      return 0
    }
  }

  // Auto-start SSE for processing jobs
  useEffect(() => {
    const processingJob = jobs.find(j => j.status === 'PROCESSING')
    if (processingJob && !sseJobId) {
      setSseJobId(processingJob.id)
    } else if (!processingJob && sseJobId) {
      setSseJobId(null)
    }
  }, [jobs, sseJobId])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
            <p className="text-gray-600 mt-1">Monitor and manage log processing jobs</p>
          </div>
          <div className="flex items-center space-x-3">
            {sseConnected && (
              <span className="flex items-center text-sm text-green-600">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
                Live Updates
              </span>
            )}
            <button
              onClick={() => setShowUploadModal(true)}
              className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Log File
            </button>
            <button
              onClick={() => refetch()}
              className="flex items-center px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex-1">
            <SearchInput
              value={searchTerm}
              onChange={setSearchTerm}
              placeholder="Search jobs by filename or ID..."
            />
          </div>
          <div className="flex gap-2">
            <select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              className="px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Status</option>
              <option value="PENDING">Pending</option>
              <option value="PROCESSING">Processing</option>
              <option value="COMPLETED">Completed</option>
              <option value="FAILED">Failed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
            <ClusterPicker
              label={false}
              clusters={clusters}
              value={filters.cluster}
              onChange={(cluster) => setFilters({ ...filters, cluster, skip: 0 })}
            />
            <select
              value={filters.limit}
              onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value) })}
              className="px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={10}>10 per page</option>
              <option value={20}>20 per page</option>
              <option value={50}>50 per page</option>
            </select>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Clock className="w-8 h-8 text-blue-600 mr-3" />
              <div>
                <p className="text-sm text-blue-600">Pending</p>
                <p className="text-xl font-bold text-blue-900">
                  {jobs.filter(j => j.status === 'PENDING').length}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Play className="w-8 h-8 text-blue-600 mr-3" />
              <div>
                <p className="text-sm text-blue-600">Processing</p>
                <p className="text-xl font-bold text-blue-900">
                  {jobs.filter(j => j.status === 'PROCESSING').length}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-green-50 p-4 rounded-lg">
            <div className="flex items-center">
              <CheckCircle className="w-8 h-8 text-green-600 mr-3" />
              <div>
                <p className="text-sm text-green-600">Completed</p>
                <p className="text-xl font-bold text-green-900">
                  {jobs.filter(j => j.status === 'COMPLETED').length}
                </p>
              </div>
            </div>
          </div>
          <div className="bg-red-50 p-4 rounded-lg">
            <div className="flex items-center">
              <XCircle className="w-8 h-8 text-red-600 mr-3" />
              <div>
                <p className="text-sm text-red-600">Failed</p>
                <p className="text-xl font-bold text-red-900">
                  {jobs.filter(j => j.status === 'FAILED').length}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Jobs List */}
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-16 bg-gray-200 rounded"></div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to load jobs</h3>
            <p className="text-gray-600">Please try again later</p>
          </div>
        ) : filteredJobs.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No jobs found"
            description={searchTerm ? 'Try adjusting your search' : 'Upload a log file to get started'}
            action={{
              label: 'Upload Log File',
              onClick: () => setShowUploadModal(true)
            }}
          />
        ) : (
          <div className="space-y-4">
            {filteredJobs.map((job: Job) => (
              <div key={job.id} className="border border-gray-200 rounded-lg hover:shadow-md transition-shadow">
                <div className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <StatusBadge status={job.status} size="sm" />
                      <div>
                        <h3 className="font-medium text-gray-900">{job.filename}</h3>
                        <p className="text-sm text-gray-500">ID: {job.id}</p>
                        {job.cluster_name && (
                          <span className="inline-flex items-center mt-1 px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-800 rounded-full">
                            <Server className="w-3 h-3 mr-1" />
                            {job.cluster_name}
                          </span>
                        )}
                        {job.status === 'COMPLETED' && getIncidentCount(job) > 0 && (
                          <Link
                            to="/incidents"
                            className="inline-flex items-center mt-1 text-sm text-blue-600 hover:text-blue-800"
                          >
                            <CheckCircle className="w-3 h-3 mr-1" />
                            {getIncidentCount(job)} incidents found
                          </Link>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => toggleJobExpansion(job.id)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        {expandedJobs.has(job.id) ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => handleViewDetails(job)}
                        className="p-1 text-gray-400 hover:text-gray-600"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      {(job.status === 'PENDING' || job.status === 'PROCESSING') && (
                        <CancelJobButton jobId={job.id} />
                      )}
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {(job.status === 'PROCESSING' || job.status === 'PENDING') && (
                    <div className="mt-3">
                      <ProgressBar 
                        progress={job.progress} 
                        size="sm"
                        color="auto"
                        showPercentage={true}
                      />
                    </div>
                  )}

                  {/* Expanded Details */}
                  {expandedJobs.has(job.id) && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium text-gray-700">File Size:</span>
                          <span className="ml-2 text-gray-600">{formatFileSize(job.file_size)}</span>
                        </div>
                        <div>
                          <span className="font-medium text-gray-700">Created:</span>
                          <span className="ml-2 text-gray-600">{formatDate(job.created_at)}</span>
                        </div>
                        {job.cluster_name && (
                          <div>
                            <span className="font-medium text-gray-700">Cluster:</span>
                            <span className="ml-2 text-gray-600">{job.cluster_name}</span>
                          </div>
                        )}
                        {job.started_at && (
                          <div>
                            <span className="font-medium text-gray-700">Started:</span>
                            <span className="ml-2 text-gray-600">{formatDate(job.started_at)}</span>
                          </div>
                        )}
                        {job.completed_at && (
                          <div>
                            <span className="font-medium text-gray-700">Completed:</span>
                            <span className="ml-2 text-gray-600">{formatDate(job.completed_at)}</span>
                          </div>
                        )}
                      </div>
                      {job.error_message && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                          <p className="text-sm font-medium text-red-800">Error Message:</p>
                          <p className="text-sm text-red-600 mt-1">{job.error_message}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Upload Log File</h3>
              <FileUploadModal
                onClose={() => setShowUploadModal(false)}
                onSuccess={() => {
                  setShowUploadModal(false)
                  queryClient.invalidateQueries({ queryKey: ['jobs'] })
                  toast.success('File uploaded successfully')
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Job Details Modal */}
      {showDetailsModal && selectedJob && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Job Details</h3>
              <JobDetailsModal
                job={selectedJob}
                onClose={() => setShowDetailsModal(false)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// File Upload Modal Component
function FileUploadModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [nodeHostname, setNodeHostname] = useState('')
  const [description, setDescription] = useState('')
  const [isUploading, setIsUploading] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: (data: { file: File; nodeHostname?: string; description?: string }) =>
      apiService.uploadLogFile(data.file, data.nodeHostname, data.description),
    onSuccess: () => {
      setIsUploading(false)
      onSuccess()
    },
    onError: () => {
      setIsUploading(false)
      toast.error('Failed to upload file')
    }
  })

  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return

    setIsUploading(true)
    uploadMutation.mutate({ file, nodeHostname, description })
  }

  const handleRemoveFile = () => {
    setFile(null)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Log File
        </label>
        <FileUpload
          onFileSelect={handleFileSelect}
          accept=".log,.txt"
          maxSize={50 * 1024 * 1024} // 50MB
        />
        {file && (
          <FilePreview
            files={[file]}
            onRemove={handleRemoveFile}
            className="mt-2"
          />
        )}
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Node Hostname (optional)
        </label>
        <input
          type="text"
          value={nodeHostname}
          onChange={(e) => setNodeHostname(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          placeholder="e.g., node-01.example.com"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Description (optional)
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
          placeholder="Describe this log file..."
        />
      </div>

      <div className="flex justify-end space-x-3 pt-4">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!file || isUploading}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {isUploading ? 'Uploading...' : 'Upload'}
        </button>
      </div>
    </form>
  )
}

// Job Details Modal Component
function JobDetailsModal({ job, onClose }: { job: Job; onClose: () => void }) {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A'
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Job ID</label>
          <p className="mt-1 text-sm text-gray-900">{job.id}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Filename</label>
          <p className="mt-1 text-sm text-gray-900">{job.filename}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Status</label>
          <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
            job.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
            job.status === 'FAILED' ? 'bg-red-100 text-red-800' :
            job.status === 'PROCESSING' ? 'bg-blue-100 text-blue-800' :
            'bg-yellow-100 text-yellow-800'
          }`}>
            {job.status}
          </span>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Progress</label>
          <div className="mt-1">
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>Progress</span>
              <span>{job.progress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${job.progress}%` }}
              ></div>
            </div>
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">File Size</label>
          <p className="mt-1 text-sm text-gray-900">{formatFileSize(job.file_size)}</p>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Created At</label>
          <p className="mt-1 text-sm text-gray-900">{formatDate(job.created_at)}</p>
        </div>
        {job.started_at && (
          <div>
            <label className="block text-sm font-medium text-gray-700">Started At</label>
            <p className="mt-1 text-sm text-gray-900">{formatDate(job.started_at)}</p>
          </div>
        )}
        {job.completed_at && (
          <div>
            <label className="block text-sm font-medium text-gray-700">Completed At</label>
            <p className="mt-1 text-sm text-gray-900">{formatDate(job.completed_at)}</p>
            {job.result_summary && (
              <div className="mt-3">
                <span className="font-medium text-gray-700">Results:</span>
                <div className="mt-1 p-2 bg-green-50 border border-green-200 rounded-md">
                  {(() => {
                    try {
                      const summary = JSON.parse(job.result_summary)
                      return (
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          {summary.total_lines !== undefined && (
                            <div className="text-gray-600">
                              <span className="font-medium">Total Lines:</span> {summary.total_lines}
                            </div>
                          )}
                          {summary.processed_lines !== undefined && (
                            <div className="text-gray-600">
                              <span className="font-medium">Processed:</span> {summary.processed_lines}
                            </div>
                          )}
                          {summary.incidents_created !== undefined && (
                            <div className="text-gray-600">
                              <span className="font-medium text-green-700">Incidents:</span>{' '}
                              <Link to="/incidents" className="text-blue-600 hover:text-blue-800 underline">
                                {summary.incidents_created} found
                              </Link>
                            </div>
                          )}
                          {summary.patterns_matched !== undefined && (
                            <div className="text-gray-600">
                              <span className="font-medium">Patterns:</span> {summary.patterns_matched}
                            </div>
                          )}
                        </div>
                      )
                    } catch {
                      return <pre className="text-sm text-gray-900">{job.result_summary}</pre>
                    }
                  })()}
                </div>
              </div>
            )}
          </div>
        )}
        {job.error_message && (
          <div>
            <label className="block text-sm font-medium text-gray-700">Error Message</label>
            <div className="mt-1 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{job.error_message}</p>
            </div>
          </div>
        )}
      </div>
      <div className="flex justify-end pt-4">
        <button
          onClick={onClose}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}

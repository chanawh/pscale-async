import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiService } from '@/services/api'
import { FileUpload, FilePreview } from '@/components/FileUpload'
import { Upload, FileText, Server, ArrowLeft, CheckCircle, AlertCircle, Activity } from 'lucide-react'
import toast from 'react-hot-toast'

type IngestionTab = 'upload' | 'stream' | 'cluster'
type ConnectionStatus = 'checking' | 'connected' | 'disconnected' | 'error'

export function LogIngestion() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<IngestionTab>('upload')
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // Connection status for cluster tab
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('checking')
  const [connectionError, setConnectionError] = useState<string | null>(null)

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadNodeHostname, setUploadNodeHostname] = useState('')
  const [uploadDescription, setUploadDescription] = useState('')

  // Stream state
  const [logLines, setLogLines] = useState('')
  const [streamNodeHostname, setStreamNodeHostname] = useState('')

  // Cluster state
  const [clusterLogPath, setClusterLogPath] = useState('/var/log/messages')
  const [clusterNodeHostname, setClusterNodeHostname] = useState('')
  
  // Check cluster connection status when cluster tab is active
  useEffect(() => {
    if (activeTab === 'cluster') {
      checkClusterConnection()
    }
  }, [activeTab])
  
  const checkClusterConnection = async () => {
    setConnectionStatus('checking')
    setConnectionError(null)
    try {
      await apiService.testClusterConnection()
      setConnectionStatus('connected')
    } catch (error: any) {
      setConnectionStatus('disconnected')
      setConnectionError(error?.message || 'Failed to connect to cluster')
    }
  }

  const handleFileSelect = (file: File) => {
    setSelectedFile(file)
  }

  const handleRemoveFile = () => {
    setSelectedFile(null)
  }

  const handleUploadSubmit = async () => {
    if (!selectedFile) {
      toast.error('Please select a file to upload')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await apiService.uploadLogFile(
        selectedFile,
        uploadNodeHostname || undefined,
        uploadDescription || undefined
      )
      toast.success(`File uploaded! Job ID: ${result.job_id.slice(0, 8)}...`)
      setSelectedFile(null)
      setUploadNodeHostname('')
      setUploadDescription('')
      navigate('/jobs')
    } catch (error) {
      toast.error('Failed to upload file')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleStreamSubmit = async () => {
    const lines = logLines.split('\n').filter(line => line.trim())
    if (lines.length === 0) {
      toast.error('Please enter at least one log line')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await apiService.streamLogLines(
        lines,
        streamNodeHostname || undefined
      )
      toast.success(`${lines.length} lines queued! Job ID: ${result.job_id.slice(0, 8)}...`)
      setLogLines('')
      setStreamNodeHostname('')
      navigate('/jobs')
    } catch (error) {
      toast.error('Failed to stream logs')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClusterSubmit = async () => {
    setIsSubmitting(true)
    
    // Retry logic with exponential backoff
    const maxRetries = 3
    let lastError: any = null
    
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const result = await apiService.ingestFromCluster(
          clusterLogPath,
          clusterNodeHostname || 'onefs-cluster'
        )
        toast.success(`Cluster ingestion started! Job ID: ${result.job_id.slice(0, 8)}...`)
        navigate('/jobs')
        return // Success - exit function
      } catch (error: any) {
        lastError = error
        
        if (attempt < maxRetries - 1) {
          // Calculate delay with exponential backoff and jitter
          const baseDelay = Math.pow(2, attempt) * 1000 // 1s, 2s, 4s
          const jitter = Math.random() * 1000 // 0-1s random jitter
          const delay = baseDelay + jitter
          
          console.log(`Retry ${attempt + 1}/${maxRetries} after ${Math.round(delay)}ms`)
          await new Promise(resolve => setTimeout(resolve, delay))
        }
      }
    }
    
    // All retries failed
    toast.error(`Failed to ingest from cluster after ${maxRetries} attempts: ${lastError?.message || 'Unknown error'}`)
    setIsSubmitting(false)
  }

  const tabs = [
    { id: 'upload', label: 'Upload File', icon: Upload },
    { id: 'stream', label: 'Stream Logs', icon: FileText },
    { id: 'cluster', label: 'From Cluster', icon: Server },
  ] as const

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Log Ingestion</h1>
          <p className="text-gray-600">Ingest logs from files, streams, or OneFS cluster</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="flex items-center px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {/* Upload File Tab */}
          {activeTab === 'upload' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Upload Log File</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Upload a log file (.log or .txt) for processing. The system will automatically
                  detect OneFS format and extract incidents.
                </p>
              </div>

              <FileUpload
                onFileSelect={handleFileSelect}
                accept=".log,.txt"
                maxSize={100 * 1024 * 1024} // 100MB
              />

              {selectedFile && (
                <FilePreview
                  files={[selectedFile]}
                  onRemove={handleRemoveFile}
                />
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Node Hostname (optional)
                  </label>
                  <input
                    type="text"
                    value={uploadNodeHostname}
                    onChange={(e) => setUploadNodeHostname(e.target.value)}
                    placeholder="e.g., Test-9700-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description (optional)
                  </label>
                  <input
                    type="text"
                    value={uploadDescription}
                    onChange={(e) => setUploadDescription(e.target.value)}
                    placeholder="Description of the log file"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <button
                  onClick={handleUploadSubmit}
                  disabled={!selectedFile || isSubmitting}
                  className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4 mr-2" />
                      Upload and Process
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Stream Logs Tab */}
          {activeTab === 'stream' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Stream Log Lines</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Paste log lines directly for immediate processing. Each line will be analyzed
                  for known patterns and incidents.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Log Lines <span className="text-red-500">*</span>
                </label>
                <textarea
                  value={logLines}
                  onChange={(e) => setLogLines(e.target.value)}
                  placeholder={`Example:
2026-03-31T07:05:44.078117+00:00 <4.3> Test-9700-1(id1) sshd[50070]: error: PAM: Authentication error
2026-03-31T07:07:00.203422+00:00 <0.5> Test-9700-1(id1) kernel: [drv.c:1499] Drive sync in progress`}
                  rows={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  {logLines.split('\n').filter(l => l.trim()).length} lines entered
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Node Hostname (optional)
                  </label>
                  <input
                    type="text"
                    value={streamNodeHostname}
                    onChange={(e) => setStreamNodeHostname(e.target.value)}
                    placeholder="e.g., Test-9700-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <button
                  onClick={handleStreamSubmit}
                  disabled={!logLines.trim() || isSubmitting}
                  className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <FileText className="w-4 h-4 mr-2" />
                      Process Log Lines
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* From Cluster Tab */}
          {activeTab === 'cluster' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Ingest from OneFS Cluster</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Fetch and process logs directly from the OneFS cluster via SSH tunnel.
                  This connects to the cluster and retrieves logs from the specified path.
                </p>
              </div>

              {/* Connection Status Indicator */}
              {connectionStatus === 'checking' && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                  <div className="flex items-center">
                    <Activity className="h-5 w-5 text-yellow-500 mr-2 flex-shrink-0 animate-pulse" />
                    <div>
                      <h4 className="text-sm font-medium text-yellow-800">Checking Connection...</h4>
                      <p className="text-sm text-yellow-700 mt-1">
                        Testing SSH connectivity to cluster
                      </p>
                    </div>
                  </div>
                </div>
              )}
              
              {connectionStatus === 'connected' && (
                <div className="bg-green-50 border border-green-200 rounded-md p-4">
                  <div className="flex">
                    <CheckCircle className="h-5 w-5 text-green-500 mr-2 flex-shrink-0" />
                    <div>
                      <h4 className="text-sm font-medium text-green-800">Cluster Connected</h4>
                      <p className="text-sm text-green-700 mt-1">
                        SSH connection established. Ready to fetch logs from the cluster.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              
              {connectionStatus === 'disconnected' && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4">
                  <div className="flex">
                    <AlertCircle className="h-5 w-5 text-red-500 mr-2 flex-shrink-0" />
                    <div className="flex-1">
                      <h4 className="text-sm font-medium text-red-800">Cluster Unreachable</h4>
                      <p className="text-sm text-red-700 mt-1">
                        {connectionError || 'Cannot connect to cluster via SSH'}
                      </p>
                      <button
                        onClick={checkClusterConnection}
                        className="mt-2 text-xs text-red-600 hover:text-red-800 underline"
                      >
                        Retry Connection
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Log Path <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={clusterLogPath}
                    onChange={(e) => setClusterLogPath(e.target.value)}
                    placeholder="/var/log/messages"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Default: /var/log/messages</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Node Hostname (optional)
                  </label>
                  <input
                    type="text"
                    value={clusterNodeHostname}
                    onChange={(e) => setClusterNodeHostname(e.target.value)}
                    placeholder="e.g., Test-9700-1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="flex items-center space-x-4">
                <button
                  onClick={handleClusterSubmit}
                  disabled={!clusterLogPath.trim() || isSubmitting || connectionStatus !== 'connected'}
                  className="flex items-center px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isSubmitting ? (
                    <>
                      <div className="animate-spin mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      Fetching...
                    </>
                  ) : connectionStatus === 'disconnected' ? (
                    <>
                      <AlertCircle className="w-4 h-4 mr-2" />
                      Cluster Unavailable
                    </>
                  ) : (
                    <>
                      <Server className="w-4 h-4 mr-2" />
                      Fetch from Cluster
                    </>
                  )}
                </button>
                {connectionStatus === 'disconnected' && (
                  <button
                    onClick={checkClusterConnection}
                    className="text-sm text-blue-600 hover:text-blue-800 underline"
                  >
                    Test Connection
                  </button>
                )}
              </div>

              <div className="bg-gray-50 border border-gray-200 rounded-md p-4">
                <div className="flex">
                  <AlertCircle className="h-5 w-5 text-gray-400 mr-2 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Note</h4>
                    <p className="text-sm text-gray-600 mt-1">
                      The SSH tunnel must be configured and running. Check the Cluster Status page
                      to verify connectivity before attempting ingestion.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

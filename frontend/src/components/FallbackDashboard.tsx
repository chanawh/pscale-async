import { Link } from 'react-router-dom'
import { 
  RefreshCw, 
  Upload, 
  FileText, 
  Activity, 
  AlertTriangle,
  Server
} from 'lucide-react'

interface FallbackDashboardProps {
  onRetry: () => void
  hasTimeouts: boolean
  errorMessage?: string
}

export function FallbackDashboard({ onRetry, hasTimeouts, errorMessage }: FallbackDashboardProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
            <p className="text-gray-600">OneFS Log Intelligence Overview</p>
          </div>
          <button
            onClick={onRetry}
            className="flex items-center px-3 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry Connection
          </button>
        </div>

        {/* Error Message */}
        <div className={`border rounded-md p-4 ${
          hasTimeouts 
            ? 'bg-yellow-50 border-yellow-200' 
            : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex">
            <div className="flex-shrink-0">
              {hasTimeouts ? (
                <AlertTriangle className="h-5 w-5 text-yellow-400" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-red-400" />
              )}
            </div>
            <div className="ml-3">
              <h3 className={`text-sm font-medium ${
                hasTimeouts ? 'text-yellow-800' : 'text-red-800'
              }`}>
                {hasTimeouts ? 'Connection Timeout' : 'Connection Error'}
              </h3>
              <div className={`mt-2 text-sm ${
                hasTimeouts ? 'text-yellow-700' : 'text-red-700'
              }`}>
                <p>
                  {hasTimeouts 
                    ? 'The dashboard requests timed out. The backend may be slow or temporarily unavailable.'
                    : 'Unable to connect to the backend. Please check if the server is running.'
                  }
                </p>
                {errorMessage && (
                  <p className="mt-1 font-mono text-xs">
                    Error: {errorMessage}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Fallback Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-lg shadow opacity-60">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Incidents</p>
              <p className="text-2xl font-bold text-gray-400">—</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-full">
              <FileText className="w-6 h-6 text-gray-400" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow opacity-60">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Critical Incidents</p>
              <p className="text-2xl font-bold text-gray-400">—</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-full">
              <AlertTriangle className="w-6 h-6 text-gray-400" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow opacity-60">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active Jobs</p>
              <p className="text-2xl font-bold text-gray-400">—</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-full">
              <Activity className="w-6 h-6 text-gray-400" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow opacity-60">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">System Health</p>
              <p className="text-2xl font-bold text-gray-400">—</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-full">
              <Server className="w-6 h-6 text-gray-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            disabled
            className="flex items-center justify-center px-4 py-3 bg-gray-300 text-gray-500 rounded-md cursor-not-allowed"
          >
            <Upload className="w-5 h-5 mr-2" />
            Upload Log File (Unavailable)
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

      {/* Troubleshooting Tips */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">Troubleshooting Tips</h3>
        <div className="space-y-2 text-sm text-blue-800">
          <p>• Check if the backend server is running</p>
          <p>• Verify your network connection</p>
          <p>• Try refreshing the page</p>
          <p>• Contact your system administrator if the issue persists</p>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useAuth } from '@/hooks/useAuth'
import { apiService } from '@/services/api'
import { LoginRequest } from '@/types'

export function Login() {
  const [isLoading, setIsLoading] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [connectivityStatus, setConnectivityStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  
  const from = location.state?.from?.pathname || '/'

  // Check backend connectivity on component mount
  useEffect(() => {
    const checkConnectivity = async () => {
      try {
        const result = await apiService.testBackendConnectivity()
        setConnectivityStatus(result.reachable ? 'connected' : 'disconnected')
        if (!result.reachable) {
          setLoginError(`Backend server is not reachable (${result.error}). Please ensure the server is running on localhost:8000.`)
        }
      } catch (error) {
        setConnectivityStatus('disconnected')
        setLoginError('Unable to test backend connectivity. Please check if the server is running.')
      }
    }

    checkConnectivity()
  }, [])

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginRequest>()

  const onSubmit = async (data: LoginRequest) => {
    console.log('Login attempt started:', data)
    setIsLoading(true)
    setLoginError(null)
    try {
      console.log('Calling login function...')
      await login(data)
      console.log('Login successful, navigating to:', from)
      navigate(from, { replace: true })
    } catch (error: any) {
      console.error('Login failed:', error)
      // Display user-friendly error message
      if (error.message?.includes('timeout')) {
        setLoginError('Login request timed out. The server may be slow or unavailable. Please try again.')
      } else if (error.message?.includes('401') || error.message?.includes('403')) {
        setLoginError('Invalid username or password.')
      } else if (error.message?.includes('500')) {
        setLoginError('Server error occurred. Please try again later.')
      } else if (!error.response) {
        setLoginError('Unable to connect to the server. Please check your network connection.')
      } else {
        setLoginError(error.message || 'Login failed. Please try again.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleRetryConnectivity = async () => {
    setConnectivityStatus('checking')
    setLoginError(null)
    try {
      const result = await apiService.testBackendConnectivity()
      setConnectivityStatus(result.reachable ? 'connected' : 'disconnected')
      if (!result.reachable) {
        setLoginError(`Backend server is not reachable (${result.error}). Please ensure the server is running on localhost:8000.`)
      }
    } catch (error) {
      setConnectivityStatus('disconnected')
      setLoginError('Unable to test backend connectivity. Please check if the server is running.')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to Log Intelligence
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            OneFS Cluster Log Monitoring Dashboard
          </p>
        </div>

        {/* Connectivity Status */}
        <div className="flex items-center justify-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${
            connectivityStatus === 'checking' ? 'bg-yellow-400 animate-pulse' :
            connectivityStatus === 'connected' ? 'bg-green-400' :
            'bg-red-400'
          }`} />
          <span className="text-sm text-gray-600">
            {connectivityStatus === 'checking' ? 'Checking server...' :
             connectivityStatus === 'connected' ? 'Server connected' :
             'Server disconnected'}
          </span>
          {connectivityStatus === 'disconnected' && (
            <button
              type="button"
              onClick={handleRetryConnectivity}
              className="text-xs text-blue-600 hover:text-blue-800 underline"
            >
              Retry
            </button>
          )}
        </div>

        {/* Error Display */}
        {loginError && (
          <div className="rounded-md bg-red-50 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Connection Error</h3>
                <div className="mt-2 text-sm text-red-700">
                  <p>{loginError}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="username" className="sr-only">
                Username
              </label>
              <input
                {...register('username', { required: 'Username is required' })}
                type="text"
                autoComplete="username"
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
                placeholder="Username"
              />
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>
            <div>
              <label htmlFor="password" className="sr-only">
                Password
              </label>
              <input
                {...register('password', { required: 'Password is required' })}
                type="password"
                autoComplete="current-password"
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
                placeholder="Password"
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading || connectivityStatus !== 'connected'}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? 'Signing in...' : 
               connectivityStatus === 'checking' ? 'Checking server...' :
               connectivityStatus === 'disconnected' ? 'Server unavailable' :
               'Sign in'}
            </button>
          </div>

          <div className="text-center">
            <p className="text-sm text-gray-600">
              Demo credentials: admin / admin123
            </p>
          </div>
        </form>
      </div>
    </div>
  )
}

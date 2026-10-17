import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiService } from '@/services/api'
import { LoginRequest, AuthTokens } from '@/types'

export function useAuth() {
  const queryClient = useQueryClient()

  // Check if user is authenticated using React Query
  const { data: isAuthenticated = false, isLoading: authLoading } = useQuery({
    queryKey: ['auth', 'isAuthenticated'],
    queryFn: () => {
      const token = localStorage.getItem('access_token')
      console.log('useAuth - checking token:', !!token)
      return !!token
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 10, // 10 minutes (renamed from cacheTime in v5)
  })

  const loginMutation = useMutation({
    mutationFn: (credentials: LoginRequest) => apiService.login(credentials),
    retry: false, // Prevent repeated timeout errors on a single login attempt
    onSuccess: (data: AuthTokens) => {
      console.log('Login mutation successful:', data)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      console.log('Tokens stored in localStorage')
      
      // Update React Query cache
      queryClient.setQueryData(['auth', 'isAuthenticated'], true)
      console.log('Authentication state updated in React Query')
      
      queryClient.invalidateQueries({ queryKey: ['auth'] })
    },
    onError: (error: any) => {
      console.error('Login mutation error:', error)
      
      // Provide user-friendly error messages for common issues
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        throw new Error('Login request timed out. The server may be slow or unavailable. Please try again.')
      } else if (error.response?.status === 401) {
        throw new Error('Invalid username or password.')
      } else if (error.response?.status === 500) {
        throw new Error('Server error occurred. Please try again later.')
      } else if (!error.response) {
        throw new Error('Unable to connect to the server. Please check your network connection.')
      }
    }
  })

  const logoutMutation = useMutation({
    mutationFn: () => apiService.logout(),
    onSuccess: () => {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      
      // Update React Query cache
      queryClient.setQueryData(['auth', 'isAuthenticated'], false)
      queryClient.clear()
    },
  })

  const refreshTokenMutation = useMutation({
    mutationFn: () => apiService.refreshToken(),
    onSuccess: (data: AuthTokens) => {
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
    },
    onError: () => {
      logoutMutation.mutate()
    },
  })

  const login = (credentials: LoginRequest) => {
    return loginMutation.mutateAsync(credentials)
  }

  const logout = () => {
    logoutMutation.mutate()
  }

  const refreshToken = () => {
    return refreshTokenMutation.mutateAsync()
  }

  return {
    isAuthenticated,
    login,
    logout,
    refreshToken,
    isLoading: authLoading || loginMutation.isLoading || logoutMutation.isLoading,
    error: loginMutation.error || logoutMutation.error,
  }
}

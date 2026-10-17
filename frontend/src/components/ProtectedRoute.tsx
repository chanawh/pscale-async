import { Navigate, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

interface ProtectedRouteProps {
  children?: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  console.log('ProtectedRoute - component mounting')
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()
  
  console.log('ProtectedRoute - state:', { 
    isAuthenticated, 
    isLoading, 
    path: location.pathname,
    hasChildren: !!children,
    hasOutlet: !children
  })

  if (isLoading) {
    console.log('ProtectedRoute - still loading auth state')
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!isAuthenticated) {
    console.log('ProtectedRoute - not authenticated, redirecting to login')
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  console.log('ProtectedRoute - authenticated, rendering content')
  console.log('ProtectedRoute - children type:', typeof children, 'children value:', children)
  // If children provided, render them (for direct usage)
  // Otherwise render Outlet (for route element usage)
  const content = children ? <>{children}</> : <Outlet />
  console.log('ProtectedRoute - rendering content type:', children ? 'children' : 'Outlet')
  return content
}

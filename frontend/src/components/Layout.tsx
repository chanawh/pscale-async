import { useState } from 'react'
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Briefcase,
  Activity,
  LogOut,
  Menu,
  X,
  Upload,
  Code,
  Server,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

function SidebarContent({ navigation, currentPath, onLogout }: {
  navigation: Array<{ name: string; href: string; icon: any }>
  currentPath: string
  onLogout: () => void
}) {
  console.log('SidebarContent - rendering with navigation:', navigation.length, 'items')
  
  return (
    <div className="flex-1 flex flex-col min-h-0 bg-white border-r border-gray-200">
      <div className="flex-1 flex flex-col pt-5 pb-4 overflow-y-auto">
        <div className="flex items-center flex-shrink-0 px-4">
          <h1 className="text-xl font-bold text-gray-900">Log Intelligence</h1>
        </div>
        <nav className="mt-5 flex-1 px-2 space-y-1">
          {navigation.map((item) => {
            const isActive = currentPath === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => console.log('Navigation clicked:', item.name, item.href)}
                className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                <item.icon className="w-5 h-5 mr-3" />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
      <div className="flex-shrink-0 flex border-t border-gray-200 p-4">
        <button
          onClick={onLogout}
          className="flex items-center w-full px-3 py-2 text-sm font-medium text-gray-600 rounded-md hover:bg-gray-100 hover:text-gray-900"
        >
          <LogOut className="w-5 h-5 mr-3" />
          Logout
        </button>
      </div>
    </div>
  )
}

function TopBar({ onMenuClick }: { onMenuClick: () => void }) {
  console.log('TopBar - rendering')
  
  return (
    <div className="lg:hidden">
      <div className="flex items-center justify-between h-16 px-4 bg-white border-b border-gray-200">
        <button
          onClick={onMenuClick}
          className="flex items-center justify-center h-10 w-10 rounded-md focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
        >
          <Menu className="h-6 w-6 text-gray-400" />
        </button>
        <h1 className="text-lg font-semibold text-gray-900">Log Intelligence</h1>
        <div className="w-10"></div>
      </div>
    </div>
  )
}

export function Layout() {
  console.log('Layout component - mounting')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Ingest Logs', href: '/ingest', icon: Upload },
    { name: 'Incidents', href: '/incidents', icon: FileText },
    { name: 'Jobs', href: '/jobs', icon: Briefcase },
    { name: 'Patterns', href: '/patterns', icon: Code },
    { name: 'Nodes', href: '/nodes', icon: Server },
    { name: 'Cluster Status', href: '/cluster', icon: Activity },
  ]

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  console.log('Layout - rendering with path:', location.pathname)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar */}
      <div className={`lg:hidden ${sidebarOpen ? 'block' : 'hidden'}`}>
        <div className="fixed inset-0 z-40 flex">
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
          <div className="relative flex-1 flex flex-col max-w-xs w-full bg-white">
            <div className="absolute top-0 right-0 -mr-12 pt-2">
              <button
                type="button"
                className="ml-1 flex items-center justify-center h-10 w-10 rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
                onClick={() => setSidebarOpen(false)}
              >
                <X className="h-6 w-6 text-white" />
              </button>
            </div>
            <SidebarContent navigation={navigation} currentPath={location.pathname} onLogout={handleLogout} />
          </div>
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0">
        <SidebarContent navigation={navigation} currentPath={location.pathname} onLogout={handleLogout} />
      </div>

      {/* Main content */}
      <div className="lg:pl-64 flex flex-col flex-1">
        <TopBar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

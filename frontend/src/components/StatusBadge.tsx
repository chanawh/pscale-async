import { CheckCircle, XCircle, AlertTriangle, Clock, Play } from 'lucide-react'

interface StatusBadgeProps {
  status: string
  size?: 'sm' | 'md' | 'lg'
  showIcon?: boolean
}

export function StatusBadge({ status, size = 'md', showIcon = true }: StatusBadgeProps) {
  const getStatusConfig = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
      case 'CONNECTED':
      case 'ONLINE':
      case 'RESOLVED':
        return {
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          icon: CheckCircle,
          iconColor: 'text-green-500'
        }
      case 'FAILED':
      case 'DISCONNECTED':
      case 'OFFLINE':
        return {
          bgColor: 'bg-red-100',
          textColor: 'text-red-800',
          icon: XCircle,
          iconColor: 'text-red-500'
        }
      case 'PROCESSING':
      case 'IN_PROGRESS':
        return {
          bgColor: 'bg-blue-100',
          textColor: 'text-blue-800',
          icon: Play,
          iconColor: 'text-blue-500'
        }
      case 'PENDING':
        return {
          bgColor: 'bg-yellow-100',
          textColor: 'text-yellow-800',
          icon: Clock,
          iconColor: 'text-yellow-500'
        }
      case 'CANCELLED':
        return {
          bgColor: 'bg-gray-200',
          textColor: 'text-gray-700',
          icon: XCircle,
          iconColor: 'text-gray-500'
        }
      case 'DEGRADED':
      case 'ESCALATED':
        return {
          bgColor: 'bg-orange-100',
          textColor: 'text-orange-800',
          icon: AlertTriangle,
          iconColor: 'text-orange-500'
        }
      default:
        return {
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-800',
          icon: AlertTriangle,
          iconColor: 'text-gray-500'
        }
    }
  }

  const config = getStatusConfig(status)
  const Icon = config.icon

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-2 text-base'
  }

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  }

  return (
    <span className={`inline-flex items-center gap-1 font-medium rounded-full ${config.bgColor} ${config.textColor} ${sizeClasses[size]}`}>
      {showIcon && <Icon className={iconSizes[size]} />}
      {status}
    </span>
  )
}

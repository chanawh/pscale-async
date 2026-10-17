interface ProgressBarProps {
  progress: number
  size?: 'sm' | 'md' | 'lg'
  color?: 'blue' | 'green' | 'yellow' | 'red' | 'gray' | 'auto'
  showPercentage?: boolean
  label?: string
  className?: string
}

export function ProgressBar({ 
  progress, 
  size = 'md', 
  color = 'blue',
  showPercentage = true,
  label,
  className = ''
}: ProgressBarProps) {
  const getColorClasses = (color: string) => {
    const colors = {
      blue: 'bg-blue-600',
      green: 'bg-green-600',
      yellow: 'bg-yellow-600',
      red: 'bg-red-600',
      gray: 'bg-gray-600',
      auto: 'bg-blue-600' // Default color, will be overridden by progress-based logic
    }
    return colors[color as keyof typeof colors] || colors.blue
  }

  const getSizeClasses = (size: string) => {
    const sizes = {
      sm: 'h-1',
      md: 'h-2',
      lg: 'h-3'
    }
    return sizes[size as keyof typeof sizes] || sizes.md
  }

  const getProgressColor = (progress: number) => {
    if (progress >= 90) return 'red'
    if (progress >= 75) return 'yellow'
    if (progress >= 50) return 'blue'
    return 'green'
  }

  const actualColor = color === 'auto' ? getProgressColor(progress) : color
  const colorClass = getColorClasses(actualColor)
  const sizeClass = getSizeClasses(size)

  return (
    <div className={`w-full ${className}`}>
      {(label || showPercentage) && (
        <div className="flex justify-between items-center mb-1">
          {label && (
            <span className="text-sm font-medium text-gray-700">{label}</span>
          )}
          {showPercentage && (
            <span className="text-sm text-gray-600">{Math.round(progress)}%</span>
          )}
        </div>
      )}
      <div className={`w-full bg-gray-200 rounded-full ${sizeClass}`}>
        <div
          className={`${colorClass} ${sizeClass} rounded-full transition-all duration-300 ease-out`}
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
    </div>
  )
}

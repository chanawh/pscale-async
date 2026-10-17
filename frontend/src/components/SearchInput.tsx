import { useState, useEffect } from 'react'
import { Search, X } from 'lucide-react'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  onClear?: () => void
  debounceMs?: number
}

export function SearchInput({ 
  value, 
  onChange, 
  placeholder = 'Search...', 
  className = '',
  onClear,
  debounceMs = 300
}: SearchInputProps) {
  const [localValue, setLocalValue] = useState(value)
  const [debounceTimer, setDebounceTimer] = useState<number | null>(null)

  const handleChange = (newValue: string) => {
    setLocalValue(newValue)
    
    // Clear existing timer
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    
    // Set new timer
    const timer = window.setTimeout(() => {
      onChange(newValue)
    }, debounceMs)
    
    setDebounceTimer(timer)
  }

  const handleClear = () => {
    setLocalValue('')
    onChange('')
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    onClear?.()
  }

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value)
  }, [value])

  return (
    <div className={`relative ${className}`}>
      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
      <input
        type="text"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
      />
      {localValue && (
        <button
          onClick={handleClear}
          className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}

export function AdvancedSearchInput({
  value,
  onChange,
  placeholder = 'Search...',
  filters,
  onFilterChange,
  className = ''
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  filters?: Array<{
    key: string
    label: string
    options: Array<{ value: string; label: string }>
    selected?: string
  }>
  onFilterChange?: (key: string, value: string) => void
  className?: string
}) {
  return (
    <div className={`space-y-3 ${className}`}>
      <SearchInput value={value} onChange={onChange} placeholder={placeholder} />
      
      {filters && filters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {filters.map((filter) => (
            <select
              key={filter.key}
              value={filter.selected || ''}
              onChange={(e) => onFilterChange?.(filter.key, e.target.value)}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">{filter.label}</option>
              {filter.options.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ))}
        </div>
      )}
    </div>
  )
}

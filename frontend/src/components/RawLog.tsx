import { useState } from 'react'
import { ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'

interface RawLogProps {
  log: string
  maxLength?: number
  className?: string
}

export function RawLog({ log, maxLength = 100, className = '' }: RawLogProps) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)

  if (!log) return null

  const isTruncated = log.length > maxLength
  const displayLog = expanded ? log : log.slice(0, maxLength)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(log)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignore copy errors
    }
  }

  return (
    <div className={`bg-gray-50 rounded-md border border-gray-200 ${className}`}>
      <div className="p-3">
        <div className="flex items-start justify-between gap-2">
          <code className="text-xs font-mono text-gray-700 break-all flex-1">
            {displayLog}
            {isTruncated && !expanded && (
              <span className="text-gray-400">...</span>
            )}
          </code>
          <button
            onClick={handleCopy}
            className="flex-shrink-0 p-1 text-gray-400 hover:text-gray-600 transition-colors"
            title="Copy full log"
          >
            {copied ? (
              <Check className="w-3 h-3 text-green-500" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </button>
        </div>
        {isTruncated && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2 flex items-center text-xs text-blue-600 hover:text-blue-800 transition-colors"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3 h-3 mr-1" />
                Show less
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3 mr-1" />
                Show more ({log.length - maxLength} more chars)
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}

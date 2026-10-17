import { useEffect, useState, useCallback } from 'react'

interface JobEvent {
  id: string
  status: string
  progress: number
  result_summary?: Record<string, number>
  error_message?: string
  started_at?: string
  completed_at?: string
  celery_status?: string
}

interface UseJobEventsOptions {
  onProgress?: (event: JobEvent) => void
  onComplete?: (event: JobEvent) => void
  onError?: (error: string) => void
}

export function useJobEvents(jobId: string | null, options: UseJobEventsOptions = {}) {
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<JobEvent | null>(null)
  const [error, setError] = useState<string | null>(null)

  const connect = useCallback(() => {
    if (!jobId) return

    const eventSource = new EventSource(`/api/v1/jobs/${jobId}/events`)

    eventSource.onopen = () => {
      setIsConnected(true)
      setError(null)
    }

    eventSource.addEventListener('progress', (event) => {
      try {
        const data: JobEvent = JSON.parse(event.data)
        setLastEvent(data)
        options.onProgress?.(data)
      } catch (err) {
        console.error('Failed to parse progress event:', err)
      }
    })

    eventSource.addEventListener('complete', (event) => {
      try {
        const data: JobEvent = JSON.parse(event.data)
        setLastEvent(data)
        setIsConnected(false)
        options.onComplete?.(data)
        eventSource.close()
      } catch (err) {
        console.error('Failed to parse complete event:', err)
      }
    })

    eventSource.addEventListener('error', (event: Event) => {
      try {
        const msgEvent = event as MessageEvent
        const data = JSON.parse(msgEvent.data)
        setError(data.error || 'Unknown error')
        setIsConnected(false)
        options.onError?.(data.error || 'Unknown error')
        eventSource.close()
      } catch (err) {
        setError('Connection error')
        setIsConnected(false)
        options.onError?.('Connection error')
      }
    })

    eventSource.onerror = () => {
      setError('EventSource connection failed')
      setIsConnected(false)
      options.onError?.('EventSource connection failed')
      eventSource.close()
    }

    return () => {
      eventSource.close()
      setIsConnected(false)
    }
  }, [jobId, options])

  useEffect(() => {
    const cleanup = connect()
    return cleanup
  }, [connect])

  return {
    isConnected,
    lastEvent,
    error,
  }
}

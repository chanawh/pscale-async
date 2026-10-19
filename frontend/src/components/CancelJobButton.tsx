import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { apiService } from '@/services/api'

interface CancelJobButtonProps {
  jobId: string
  className?: string
  title?: string
}

/**
 * Confirm-then-cancel for a processing job, wired to the real
 * POST /api/v1/jobs/{job_id}/cancel endpoint.
 *
 * First click arms the button ("Confirm?"); second click fires the
 * cancel. Every failure mode in the backend's contract gets an honest
 * message instead of a generic "failed":
 *   404 — job gone (may have been deleted)
 *   409 — job already terminal; the list refreshes to show its real state
 *   422 — job predates Celery task tracking; nothing to revoke
 *   503 — broker unreachable; the job keeps its state, retry is safe
 */
export function CancelJobButton({ jobId, className, title = 'Cancel job' }: CancelJobButtonProps) {
  const [armed, setArmed] = useState(false)
  const armTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const queryClient = useQueryClient()

  useEffect(() => {
    return () => {
      if (armTimer.current) clearTimeout(armTimer.current)
    }
  }, [])

  const disarm = () => {
    setArmed(false)
    if (armTimer.current) {
      clearTimeout(armTimer.current)
      armTimer.current = null
    }
  }

  const mutation = useMutation({
    mutationFn: (id: string) => apiService.cancelJob(id),
    onSuccess: (data) => {
      const n = data.revoked_task_ids?.length ?? 0
      toast.success(`Job cancelled — ${n} Celery task${n === 1 ? '' : 's'} revoked`)
      disarm()
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error: unknown) => {
      const status = (error as { response?: { status?: number } })?.response?.status
      disarm()
      switch (status) {
        case 404:
          toast.error('Job not found — it may have been deleted')
          void queryClient.invalidateQueries({ queryKey: ['jobs'] })
          break
        case 409:
          // The job reached a terminal state out from under the UI;
          // refresh so the row shows its real status.
          toast.error('Job already finished — nothing to cancel')
          void queryClient.invalidateQueries({ queryKey: ['jobs'] })
          break
        case 422:
          toast.error('Job predates task tracking — nothing to revoke')
          break
        case 503:
          toast.error('Task queue unreachable — job was not cancelled, you can retry')
          break
        default:
          toast.error('Failed to cancel job')
      }
    },
  })

  const handleClick = () => {
    if (mutation.isLoading) return
    if (!armed) {
      setArmed(true)
      armTimer.current = setTimeout(disarm, 4000)
      return
    }
    mutation.mutate(jobId)
  }

  const handleBlur = () => {
    // Disarm when focus leaves, so a stray armed button can't surprise.
    disarm()
  }

  if (armed) {
    return (
      <button
        onClick={handleClick}
        onBlur={handleBlur}
        disabled={mutation.isLoading}
        className="px-2 py-1 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700 disabled:opacity-50 whitespace-nowrap"
        title="Click again to confirm cancellation"
      >
        {mutation.isLoading ? (
          <span className="inline-flex items-center">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" />
            Cancelling…
          </span>
        ) : (
          'Confirm cancel?'
        )}
      </button>
    )
  }

  return (
    <button
      onClick={handleClick}
      className={className ?? 'p-1 text-red-400 hover:text-red-600'}
      title={title}
      aria-label={title}
    >
      <Trash2 className="w-4 h-4" />
    </button>
  )
}

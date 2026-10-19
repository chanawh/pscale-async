import { useQuery } from '@tanstack/react-query'
import { apiService } from '@/services/api'

/**
 * Cluster names known to the UI.
 *
 * The backend exposes no cluster-listing endpoint (targets come from
 * ONEFS_TARGETS / ONEFS_TARGETS_FILE server-side), so the picker is
 * populated from the distinct `cluster_name` values present on jobs.
 * In single-cluster mode every job has `cluster_name: null` and this
 * returns an empty list — callers should hide the picker then.
 */
export function useClusters() {
  const { data, isLoading } = useQuery({
    queryKey: ['clusters'],
    queryFn: async () => {
      const res = await apiService.getJobs({ limit: 200 })
      const names = new Set<string>()
      for (const job of res.jobs ?? []) {
        if (job.cluster_name) names.add(job.cluster_name)
      }
      return [...names].sort()
    },
    staleTime: 1000 * 60 * 5,
    retry: 1,
  })

  return { clusters: data ?? [], isLoadingClusters: isLoading }
}

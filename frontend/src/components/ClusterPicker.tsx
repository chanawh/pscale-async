import { Server } from 'lucide-react'

interface ClusterPickerProps {
  value: string
  onChange: (cluster: string) => void
  clusters: string[]
  label?: boolean
}

/**
 * Multi-cluster filter dropdown. Renders nothing when the backend is
 * single-cluster (no named clusters seen on jobs) — the `?cluster=`
 * filter then stays unset and every job/incident matches.
 */
export function ClusterPicker({ value, onChange, clusters, label = true }: ClusterPickerProps) {
  if (clusters.length === 0) return null

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          <span className="inline-flex items-center">
            <Server className="w-3 h-3 mr-1" />
            Cluster
          </span>
        </label>
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-label="Filter by cluster"
      >
        <option value="">All clusters</option>
        {clusters.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </div>
  )
}

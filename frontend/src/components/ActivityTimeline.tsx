import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Clock,
  User,
  MessageSquare,
  ArrowUpCircle,
  CheckCircle,
  PlayCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  History
} from 'lucide-react'
import { apiService } from '@/services/api'

interface ActivityTimelineProps {
  incidentId: number
}

const actionIcons: Record<string, React.ReactNode> = {
  START_WORK: <PlayCircle className="w-5 h-5 text-blue-500" />,
  ESCALATE: <ArrowUpCircle className="w-5 h-5 text-purple-500" />,
  RESOLVE: <CheckCircle className="w-5 h-5 text-green-500" />,
  COMMENT: <MessageSquare className="w-5 h-5 text-gray-500" />,
  ASSIGN: <User className="w-5 h-5 text-orange-500" />,
}

const actionColors: Record<string, string> = {
  START_WORK: 'bg-blue-50 border-blue-200',
  ESCALATE: 'bg-purple-50 border-purple-200',
  RESOLVE: 'bg-green-50 border-green-200',
  COMMENT: 'bg-gray-50 border-gray-200',
  ASSIGN: 'bg-orange-50 border-orange-200',
}

const actionLabels: Record<string, string> = {
  START_WORK: 'Started Work',
  ESCALATE: 'Escalated',
  RESOLVE: 'Resolved',
  COMMENT: 'Commented',
  ASSIGN: 'Assigned',
}

export function ActivityTimeline({ incidentId }: ActivityTimelineProps) {
  const [expandedActivity, setExpandedActivity] = useState<number | null>(null)

  const { data: activityData, isLoading } = useQuery({
    queryKey: ['incident-activity', incidentId],
    queryFn: () => apiService.getIncidentActivity(incidentId),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
        <span className="ml-2 text-gray-500">Loading activity...</span>
      </div>
    )
  }

  if (!activityData?.activities?.length) {
    return (
      <div className="text-center py-8">
        <History className="w-10 h-10 text-gray-300 mx-auto mb-2" />
        <p className="text-gray-500">No activity recorded yet</p>
        <p className="text-sm text-gray-400 mt-1">
          Actions like status changes will appear here
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-medium text-gray-900 flex items-center">
        <History className="w-4 h-4 mr-2" />
        Activity History ({activityData.total} entries)
      </h3>

      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-6 top-0 bottom-0 w-0.5 bg-gray-200" />

        <div className="space-y-4">
          {activityData.activities.map((activity) => {
            const isExpanded = expandedActivity === activity.id
            const hasDetails = activity.details && activity.details !== '{}'

            return (
              <div key={activity.id} className="relative flex items-start">
                {/* Icon */}
                <div className="relative z-10 flex-shrink-0 w-12 h-12 flex items-center justify-center bg-white rounded-full border-2 border-gray-100">
                  {actionIcons[activity.action_type] || (
                    <AlertCircle className="w-5 h-5 text-gray-400" />
                  )}
                </div>

                {/* Content */}
                <div className="ml-4 flex-1 min-w-0">
                  <div
                    className={`p-3 rounded-lg border ${
                      actionColors[activity.action_type] || 'bg-white border-gray-200'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium text-gray-900">
                          {actionLabels[activity.action_type] || activity.action_type}
                        </p>
                        <p className="text-sm text-gray-600 mt-1">
                          {activity.description}
                        </p>
                      </div>
                      <div className="flex items-center text-xs text-gray-400">
                        <Clock className="w-3 h-3 mr-1" />
                        {new Date(activity.created_at).toLocaleString()}
                      </div>
                    </div>

                    {/* Details section */}
                    {hasDetails && (
                      <div className="mt-2">
                        <button
                          onClick={() =>
                            setExpandedActivity(isExpanded ? null : activity.id)
                          }
                          className="flex items-center text-xs text-blue-600 hover:text-blue-800"
                        >
                          {isExpanded ? (
                            <>
                              <ChevronUp className="w-3 h-3 mr-1" />
                              Hide details
                            </>
                          ) : (
                            <>
                              <ChevronDown className="w-3 h-3 mr-1" />
                              Show details
                            </>
                          )}
                        </button>

                        {isExpanded && (
                          <div className="mt-2 p-2 bg-white rounded border border-gray-200">
                            <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                              {(() => {
                                try {
                                  const parsed = JSON.parse(activity.details || '{}')
                                  return JSON.stringify(parsed, null, 2)
                                } catch {
                                  return activity.details
                                }
                              })()}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}

                    {/* User info */}
                    {activity.user_id && activity.user_id !== 'current_user' && (
                      <div className="mt-2 flex items-center text-xs text-gray-500">
                        <User className="w-3 h-3 mr-1" />
                        By {activity.user_id}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

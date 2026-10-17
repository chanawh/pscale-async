import { useState } from 'react'
import { X, AlertTriangle, Users, Clock } from 'lucide-react'
import toast from 'react-hot-toast'

interface EscalationDetails {
  escalation_reason: string
  target_level?: string
  urgency?: string
  assigned_team?: string
}

interface EscalateModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (details: EscalationDetails) => void
  incidentTitle: string
}

export function EscalateModal({ isOpen, onClose, onSubmit, incidentTitle }: EscalateModalProps) {
  const [escalationReason, setEscalationReason] = useState('')
  const [targetLevel, setTargetLevel] = useState('')
  const [urgency, setUrgency] = useState('')
  const [assignedTeam, setAssignedTeam] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!escalationReason.trim()) {
      toast.error('Escalation reason is required')
      return
    }
    
    const details: EscalationDetails = {
      escalation_reason: escalationReason,
      target_level: targetLevel || undefined,
      urgency: urgency || undefined,
      assigned_team: assignedTeam || undefined
    }
    
    onSubmit(details)
    onClose()
    
    // Reset form
    setEscalationReason('')
    setTargetLevel('')
    setUrgency('')
    setAssignedTeam('')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-6 h-6 text-orange-500" />
            <h2 className="text-xl font-semibold text-gray-900">Escalate: {incidentTitle}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Escalation Reason *
            </label>
            <textarea
              value={escalationReason}
              onChange={(e) => setEscalationReason(e.target.value)}
              placeholder="Explain why this incident needs to be escalated..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Target Level
              </label>
              <select
                value={targetLevel}
                onChange={(e) => setTargetLevel(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Level</option>
                <option value="L1">L1 - Senior Management</option>
                <option value="L2">L2 - Department Head</option>
                <option value="L3">L3 - External Vendor</option>
                <option value="team">Team Lead</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Urgency
              </label>
              <select
                value={urgency}
                onChange={(e) => setUrgency(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Urgency</option>
                <option value="critical">Critical - Immediate</option>
                <option value="high">High - Within 4 hours</option>
                <option value="medium">Medium - Within 24 hours</option>
                <option value="low">Low - Within 72 hours</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Assigned Team
              </label>
              <select
                value={assignedTeam}
                onChange={(e) => setAssignedTeam(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Select Team</option>
                <option value="security">Security Team</option>
                <option value="infrastructure">Infrastructure Team</option>
                <option value="application">Application Team</option>
                <option value="database">Database Team</option>
                <option value="network">Network Team</option>
                <option value="external">External Vendor</option>
              </select>
            </div>
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <div className="flex items-start space-x-2">
              <Users className="w-5 h-5 text-yellow-600 mt-0.5" />
              <div className="text-sm text-yellow-800">
                <strong>Important:</strong> Escalation should only be used for incidents that require additional expertise, resources, or authority beyond the current assignee's capabilities.
              </div>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 transition-colors"
            >
              Escalate Incident
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'
import { X, AlertTriangle, Clock, User } from 'lucide-react'
import toast from 'react-hot-toast'

interface WorkDetails {
  work_description?: string
  estimated_hours?: number
  work_type?: string
  tools_used?: string[]
}

interface WorkDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (details: WorkDetails) => void
  incidentTitle: string
}

export function WorkDetailsModal({ isOpen, onClose, onSubmit, incidentTitle }: WorkDetailsModalProps) {
  const [workDescription, setWorkDescription] = useState('')
  const [estimatedHours, setEstimatedHours] = useState('')
  const [workType, setWorkType] = useState('investigation')
  const [toolsUsed, setToolsUsed] = useState<string[]>([])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    const details: WorkDetails = {
      work_description: workDescription || undefined,
      estimated_hours: estimatedHours ? parseFloat(estimatedHours) : undefined,
      work_type: workType || undefined,
      tools_used: toolsUsed.length > 0 ? toolsUsed : undefined
    }
    
    onSubmit(details)
    onClose()
    
    // Reset form
    setWorkDescription('')
    setEstimatedHours('')
    setWorkType('investigation')
    setToolsUsed([])
  }

  const addTool = (tool: string) => {
    if (toolsUsed.includes(tool)) return
    setToolsUsed([...toolsUsed, tool])
  }

  const removeTool = (tool: string) => {
    setToolsUsed(toolsUsed.filter(t => t !== tool))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">Start Work: {incidentTitle}</h2>
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
              Work Description
            </label>
            <textarea
              value={workDescription}
              onChange={(e) => setWorkDescription(e.target.value)}
              placeholder="Describe what work you're doing on this incident..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={4}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Estimated Hours
              </label>
              <input
                type="number"
                step="0.5"
                value={estimatedHours}
                onChange={(e) => setEstimatedHours(e.target.value)}
                placeholder="2.0"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Work Type
              </label>
              <select
                value={workType}
                onChange={(e) => setWorkType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="investigation">Investigation</option>
                <option value="fix">Fix</option>
                <option value="monitoring">Monitoring</option>
                <option value="patch">Patch</option>
                <option value="upgrade">Upgrade</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tools Used
            </label>
            <div className="space-y-2">
              {['log-analyzer', 'ssh', 'wireshark', 'custom-script', 'manual-review'].map((tool) => (
                <label key={tool} className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={toolsUsed.includes(tool)}
                    onChange={() => addTool(tool)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{tool}</span>
                </label>
              ))}
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
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Start Work
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

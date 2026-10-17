export interface Incident {
  id: number
  title: string
  description: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  status: 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'ESCALATED'
  raw_log: string
  processed_at: string
  created_at: string
  updated_at?: string
  node?: Node
  pattern?: Pattern
  job_id?: string
}

export interface Node {
  id: number
  hostname: string
  ip_address?: string
  node_type?: string
  version?: string
  description?: string
  created_at: string
  updated_at?: string
  incident_count?: number
}

export interface Pattern {
  id: number
  name: string
  description?: string
  regex_pattern: string
  category?: string
  severity_level: string
  is_active: boolean
  created_at: string
  updated_at?: string
  incident_count?: number
}

export interface Job {
  id: string
  filename: string
  file_size?: number
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED'
  progress: number
  result_summary?: string
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at?: string
}

export interface ClusterNode {
  id: string
  hostname: string
  status: 'online' | 'offline' | 'degraded'
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  last_seen: string
  version: string
  role: string
}

export interface ClusterMetrics {
  uptime: string
  cpu_usage: number
  memory_usage: number
  disk_usage?: number
  connection_type?: string
}

export interface ClusterStatus {
  status: 'connected' | 'disconnected' | 'error'
  cluster?: {
    hostname: string
    version: string
    nodes: number
    status?: string
    last_restart?: string
  }
  nodes?: ClusterNode[]
  metrics?: ClusterMetrics
  tunnel_host?: string
  message?: string
}

export interface Summary {
  window_hours: number
  start_time: string
  end_time: string
  summary: Record<string, Record<string, number>>
}

export interface Escalation {
  id: number
  title: string
  severity: string
  status: string
  created_at: string
  node?: string
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  username: string
  password: string
}

export interface ApiResponse<T> {
  data?: T
  error?: string
  message?: string
  total?: number
  skip?: number
  limit?: number
}

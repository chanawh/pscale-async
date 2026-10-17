import axios, { AxiosInstance, AxiosResponse } from 'axios'
import toast from 'react-hot-toast'
import { 
  Incident, 
  Job, 
  ClusterStatus, 
  Summary, 
  Escalation,
  Pattern,
  Node,
  LoginRequest,
  AuthTokens
} from '@/types'

class ApiService {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      // No baseURL - use relative paths for Vite proxy to handle routing
      timeout: 60000, // 60s hardcoded - no environment dependency
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      (error) => {
        return Promise.reject(error)
      }
    )

    // Response interceptor for error handling - skip auth endpoints to avoid duplicates
    this.client.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error) => {
        // Skip toast for auth endpoints (login handles its own errors)
        const isAuthEndpoint = error.config?.url?.includes('/auth/')
        if (!isAuthEndpoint) {
          const message = error.response?.data?.detail || error.message || 'An error occurred'
          toast.error(message)
        }
        
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          window.location.href = '/login'
        }
        
        return Promise.reject(error)
      }
    )
  }

  // Auth endpoints
  async login(credentials: LoginRequest): Promise<AuthTokens> {
    console.log('API: Starting login request with 60s timeout (DIRECT CONNECTION)')
    const startTime = Date.now()
    
    try {
      const response = await this.client.post('/api/v1/auth/login', credentials, {
        timeout: 60000 // Explicit 60s override - bypass all other settings
      })
      console.log(`API: Login request completed in ${Date.now() - startTime}ms`)
      return response.data
    } catch (error: any) {
      console.log(`API: Login request failed after ${Date.now() - startTime}ms:`, error.message)
      throw error
    }
  }

  async refreshToken(): Promise<AuthTokens> {
    const refreshToken = localStorage.getItem('refresh_token')
    const response = await this.client.post('/api/v1/auth/refresh', {
      refresh_token: refreshToken
    })
    return response.data
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/api/v1/auth/logout')
    } catch (error) {
      // Don't throw error for logout - we still want to clear local storage
      // This handles cases where the backend might be down or endpoint doesn't exist
      console.warn('Logout endpoint failed, proceeding with client-side logout:', error)
    }
  }

  // Health check
  async healthCheck(): Promise<{ status: string; database: string; celery: string }> {
    const response = await this.client.get('/health')
    return response.data
  }

  // Backend connectivity test
  async testBackendConnectivity(): Promise<{ reachable: boolean; responseTime: number; error?: string }> {
    console.log('API: Testing backend connectivity (DIRECT CONNECTION)...')
    const startTime = Date.now()
    
    try {
      await this.client.get('/health', { 
        timeout: 5000 // Short timeout for connectivity test
      })
      const responseTime = Date.now() - startTime
      console.log(`API: Backend connectivity test passed in ${responseTime}ms`)
      return { reachable: true, responseTime }
    } catch (error: any) {
      const responseTime = Date.now() - startTime
      const errorMsg = error.message || 'Unknown error'
      console.log(`API: Backend connectivity test failed after ${responseTime}ms:`, errorMsg)
      return { reachable: false, responseTime, error: errorMsg }
    }
  }

  // Cluster endpoints
  async getClusterStatus(): Promise<ClusterStatus> {
    const response = await this.client.get('/api/v1/cluster/status')
    return response.data
  }

  async getClusterNodes(): Promise<{ status: string; node_status?: string; node_config?: string; cluster_ip?: string; message?: string }> {
    const response = await this.client.get('/api/v1/cluster/nodes')
    return response.data
  }

  async testClusterConnection(): Promise<{ success: boolean; message: string; details?: any }> {
    const response = await this.client.get('/api/v1/cluster/test-connection')
    return response.data
  }

  async ingestFromCluster(logPath: string, nodeHostname: string): Promise<{ job_id: string }> {
    const params = new URLSearchParams()
    params.append('log_path', logPath)
    params.append('node_hostname', nodeHostname)
    const response = await this.client.post(`/api/v1/ingest/cluster?${params.toString()}`)
    return response.data
  }

  // Incident endpoints
  async getIncidents(params?: {
    severity?: string
    status?: string
    limit?: number
    skip?: number
  }): Promise<{
    total: number
    skip: number
    limit: number
    incidents: Incident[]
  }> {
    const response = await this.client.get('/api/v1/incidents', { params })
    return response.data
  }

  async getIncident(id: number): Promise<Incident> {
    const response = await this.client.get(`/api/v1/incidents/${id}`)
    return response.data
  }

  async updateIncidentStatus(id: number, status: string): Promise<Incident> {
    const response = await this.client.put(`/api/v1/incidents/${id}/status?new_status=${status}`)
    return response.data
  }

  // Job endpoints
  async getJobs(params?: {
    status?: string
    limit?: number
    skip?: number
  }): Promise<{
    total: number
    skip: number
    limit: number
    jobs: Job[]
  }> {
    const response = await this.client.get('/api/v1/jobs', { params })
    return response.data
  }

  async getJob(id: string): Promise<Job> {
    const response = await this.client.get(`/api/v1/jobs/${id}`)
    return response.data
  }

  async cancelJob(id: string): Promise<void> {
    await this.client.post(`/api/v1/jobs/${id}/cancel`)
  }

  async uploadLogFile(file: File, nodeHostname?: string, description?: string): Promise<{ job_id: string }> {
    const formData = new FormData()
    formData.append('file', file)
    if (nodeHostname) formData.append('node_hostname', nodeHostname)
    if (description) formData.append('description', description)

    const response = await this.client.post('/api/v1/ingest', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  async streamLogLines(logLines: string[], nodeHostname?: string): Promise<{ job_id: string }> {
    const response = await this.client.post('/api/v1/ingest/stream', {
      log_lines: logLines,
      node_hostname: nodeHostname
    })
    return response.data
  }

  // Analytics endpoints
  async getSummary(windowHours?: number, severity?: string): Promise<Summary> {
    const params: any = {}
    if (windowHours) params.window_hours = windowHours
    if (severity) params.severity = severity
    
    const response = await this.client.get('/api/v1/summary', { params })
    return response.data
  }

  async getEscalations(): Promise<{ escalations: Escalation[] }> {
    const response = await this.client.get('/api/v1/escalations')
    return response.data
  }

  // Pattern endpoints
  async getPatterns(params?: {
    category?: string
    severity?: string
    is_active?: boolean
    limit?: number
    skip?: number
  }): Promise<{
    total: number
    skip: number
    limit: number
    patterns: Pattern[]
  }> {
    const response = await this.client.get('/api/v1/patterns', { params })
    return response.data
  }

  async getPattern(id: number): Promise<Pattern> {
    const response = await this.client.get(`/api/v1/patterns/${id}`)
    return response.data
  }

  async createPattern(data: {
    name: string
    description?: string
    regex_pattern: string
    category?: string
    severity_level: string
  }): Promise<Pattern> {
    const response = await this.client.post('/api/v1/patterns', data)
    return response.data
  }

  async updatePattern(id: number, data: Partial<Pattern>): Promise<Pattern> {
    const response = await this.client.put(`/api/v1/patterns/${id}`, data)
    return response.data
  }

  async togglePattern(id: number, isActive: boolean): Promise<Pattern> {
    const response = await this.client.put(`/api/v1/patterns/${id}/toggle`, { is_active: isActive })
    return response.data
  }

  async deletePattern(id: number): Promise<void> {
    await this.client.delete(`/api/v1/patterns/${id}`)
  }

  async testPattern(regexPattern: string, testLine: string): Promise<{
    matches: boolean
    matched_text?: string
    groups: string[]
  }> {
    const response = await this.client.post('/api/v1/patterns/test', {
      regex_pattern: regexPattern,
      test_line: testLine
    })
    return response.data
  }

  async getPatternCategories(): Promise<string[]> {
    const response = await this.client.get('/api/v1/patterns/categories')
    return response.data
  }

  // Node endpoints
  async getNodes(params?: {
    node_type?: string
    limit?: number
    skip?: number
  }): Promise<{
    total: number
    skip: number
    limit: number
    nodes: Node[]
  }> {
    const response = await this.client.get('/api/v1/nodes', { params })
    return response.data
  }

  async getNode(id: number): Promise<Node> {
    const response = await this.client.get(`/api/v1/nodes/${id}`)
    return response.data
  }

  async getNodeIncidents(
    id: number,
    params?: {
      status?: string
      severity?: string
      limit?: number
      skip?: number
    }
  ): Promise<{
    total: number
    skip: number
    limit: number
    node: { id: number; hostname: string; ip_address?: string }
    incidents: Array<{
      id: number
      title: string
      description: string
      severity: string
      status: string
      created_at: string
      pattern?: string
    }>
  }> {
    const response = await this.client.get(`/api/v1/nodes/${id}/incidents`, { params })
    return response.data
  }

  async createNode(data: {
    hostname: string
    ip_address?: string
    node_type?: string
    version?: string
    description?: string
  }): Promise<Node> {
    const response = await this.client.post('/api/v1/nodes', data)
    return response.data
  }

  async updateNode(id: number, data: Partial<Node>): Promise<Node> {
    const response = await this.client.put(`/api/v1/nodes/${id}`, data)
    return response.data
  }

  async deleteNode(id: number): Promise<void> {
    await this.client.delete(`/api/v1/nodes/${id}`)
  }

  async getNodeTypes(): Promise<string[]> {
    const response = await this.client.get('/api/v1/nodes/types/list')
    return response.data
  }

  // Incident Activity endpoints
  async getIncidentActivity(incidentId: number): Promise<{
    total: number
    skip: number
    limit: number
    incident_id: number
    activities: Array<{
      id: number
      action_type: string
      description: string
      details?: string
      user_id?: string
      created_at: string
    }>
  }> {
    const response = await this.client.get(`/api/v1/incidents/${incidentId}/activity`)
    return response.data
  }

  // Database Admin endpoints
  async executeQuery(query: string, limit: number = 1000): Promise<{
    columns: string[]
    rows: Record<string, any>[]
    row_count: number
    execution_time_ms: number
    query: string
  }> {
    const response = await this.client.post('/api/v1/admin/query', { query, limit })
    return response.data
  }

  async getTables(): Promise<Array<{
    name: string
    column_count: number
    row_count: number | null
  }>> {
    const response = await this.client.get('/api/v1/admin/tables')
    return response.data
  }

  async getTableSchema(tableName: string): Promise<{
    name: string
    columns: Array<{
      name: string
      type: string
      nullable: boolean
      default: string | null
      primary_key: boolean
    }>
    indexes: Array<{
      name: string
      columns: string[]
      unique: boolean
    }>
    foreign_keys: Array<{
      name: string
      constrained_columns: string[]
      referred_table: string
      referred_columns: string[]
    }>
    row_count: number | null
  }> {
    const response = await this.client.get(`/api/v1/admin/schema/${tableName}`)
    return response.data
  }

  async getFullSchema(): Promise<{
    tables: Array<{
      name: string
      columns: Array<{
        name: string
        type: string
        nullable: boolean
        primary_key: boolean
      }>
      row_count: number | null
    }>
  }> {
    const response = await this.client.get('/api/v1/admin/schema')
    return response.data
  }

  async getQuickQueries(): Promise<Array<{
    name: string
    description: string
    query: string
  }>> {
    const response = await this.client.get('/api/v1/admin/quick-queries')
    return response.data
  }
}

export const apiService = new ApiService()

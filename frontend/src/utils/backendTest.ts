// Backend connectivity testing utility

export interface ConnectivityTestResult {
  reachable: boolean
  responseTime: number
  error?: string
  method: 'direct' | 'proxy'
}

export async function testBackendConnectivity(url?: string): Promise<ConnectivityTestResult> {
  const testUrl = url || 'http://localhost:8000'
  const startTime = Date.now()
  
  console.log(`Testing backend connectivity to: ${testUrl}`)
  
  try {
    // Test the health endpoint directly
    const response = await fetch(`${testUrl}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(5000) // 5 second timeout for test
    })
    
    const responseTime = Date.now() - startTime
    
    if (response.ok) {
      console.log(`Backend connectivity test passed in ${responseTime}ms`)
      return {
        reachable: true,
        responseTime,
        method: 'direct'
      }
    } else {
      const error = `HTTP ${response.status}: ${response.statusText}`
      console.log(`Backend connectivity test failed: ${error}`)
      return {
        reachable: false,
        responseTime,
        error,
        method: 'direct'
      }
    }
  } catch (error: any) {
    const responseTime = Date.now() - startTime
    const errorMsg = error.name === 'AbortError' ? 'Request timed out' : error.message
    console.log(`Backend connectivity test failed after ${responseTime}ms: ${errorMsg}`)
    return {
      reachable: false,
      responseTime,
      error: errorMsg,
      method: 'direct'
    }
  }
}

export async function testProxyConnectivity(): Promise<ConnectivityTestResult> {
  const startTime = Date.now()
  
  console.log('Testing backend connectivity through Vite proxy')
  
  try {
    // Test through the Vite proxy
    const response = await fetch('/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(5000) // 5 second timeout for test
    })
    
    const responseTime = Date.now() - startTime
    
    if (response.ok) {
      console.log(`Proxy connectivity test passed in ${responseTime}ms`)
      return {
        reachable: true,
        responseTime,
        method: 'proxy'
      }
    } else {
      const error = `HTTP ${response.status}: ${response.statusText}`
      console.log(`Proxy connectivity test failed: ${error}`)
      return {
        reachable: false,
        responseTime,
        error,
        method: 'proxy'
      }
    }
  } catch (error: any) {
    const responseTime = Date.now() - startTime
    const errorMsg = error.name === 'AbortError' ? 'Request timed out' : error.message
    console.log(`Proxy connectivity test failed after ${responseTime}ms: ${errorMsg}`)
    return {
      reachable: false,
      responseTime,
      error: errorMsg,
      method: 'proxy'
    }
  }
}

export async function comprehensiveConnectivityTest(): Promise<{
  direct: ConnectivityTestResult
  proxy: ConnectivityTestResult
  recommendation: string
}> {
  console.log('Running comprehensive connectivity test...')
  
  const [direct, proxy] = await Promise.all([
    testBackendConnectivity(),
    testProxyConnectivity()
  ])
  
  let recommendation = ''
  
  if (direct.reachable && proxy.reachable) {
    recommendation = 'Both direct and proxy connections are working correctly.'
  } else if (direct.reachable && !proxy.reachable) {
    recommendation = 'Direct connection works but proxy fails. Check Vite configuration.'
  } else if (!direct.reachable && proxy.reachable) {
    recommendation = 'Proxy connection works but direct fails. Backend may be expecting proxy requests.'
  } else {
    recommendation = 'Both connections failed. Check if backend is running on localhost:8000.'
  }
  
  return {
    direct,
    proxy,
    recommendation
  }
}

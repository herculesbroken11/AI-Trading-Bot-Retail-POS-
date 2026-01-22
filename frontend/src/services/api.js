const API_BASE = window.location.origin

async function fetchJSON(url, options = {}) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return await response.json()
  } catch (error) {
    console.error('API Error:', error)
    throw error
  }
}

export async function getAccountId() {
  try {
    const accounts = await fetchJSON(`${API_BASE}/orders/accounts`)
    if (accounts && accounts.length > 0) {
      const account = accounts[0]
      return account.securitiesAccount?.accountNumber || account.accountNumber || null
    }
    return null
  } catch (error) {
    console.error('Failed to get account ID:', error)
    return null
  }
}

export async function getAutomationStatus() {
  return fetchJSON(`${API_BASE}/automation/status`)
}

export async function startAutomation() {
  return fetchJSON(`${API_BASE}/automation/start`, { method: 'POST' })
}

export async function stopAutomation() {
  return fetchJSON(`${API_BASE}/automation/stop`, { method: 'POST' })
}

export async function getPositions() {
  return fetchJSON(`${API_BASE}/positions/active`)
}

export async function getDailyReport(accountId) {
  if (!accountId) return null
  return fetchJSON(`${API_BASE}/reports/daily?accountId=${accountId}`)
}

export async function getComplianceReport(startDate, endDate) {
  return fetchJSON(`${API_BASE}/reports/compliance?start_date=${startDate}&end_date=${endDate}`)
}

export async function getPerformanceAnalysis(days = 30) {
  return fetchJSON(`${API_BASE}/optimization/performance?days=${days}`)
}

export async function getSetupWeights() {
  return fetchJSON(`${API_BASE}/optimization/setup-weights`)
}

export async function getOptimizedParameters() {
  return fetchJSON(`${API_BASE}/optimization/parameters`)
}

export async function getOptimizationSummary() {
  return fetchJSON(`${API_BASE}/optimization/summary`)
}

export async function adjustSetupWeights(minTrades = 10) {
  return fetchJSON(`${API_BASE}/optimization/adjust-weights`, {
    method: 'POST',
    body: JSON.stringify({ min_trades: minTrades })
  })
}

export async function optimizeParameters() {
  return fetchJSON(`${API_BASE}/optimization/optimize-parameters`, {
    method: 'POST'
  })
}

export async function getActivityLogs(limit = 50) {
  return fetchJSON(`${API_BASE}/activity/logs?limit=${limit}`)
}

export async function getRulesStatus() {
  return fetchJSON(`${API_BASE}/activity/rules/status`)
}

export async function getWatchlist() {
  return fetchJSON(`${API_BASE}/charts/watchlist`)
}

export async function getChartData(symbol, timeframe = '1min') {
  // Parse timeframe
  // Note: Schwab API supports various frequencies
  // Request enough days to ensure we have 200+ candles for SMA200 calculation
  // After filtering to 8 AM - 4:30 PM ET, we get ~510 minutes per day
  // The backend will automatically adjust period_value if needed
  const [periodValue, periodType, frequency] = (() => {
    switch (timeframe) {
      case '1min': return [20, 'day', 1]  // Request 20 days for multi-day view when zoomed out
      case '2min': return [20, 'day', 1]  // 2min not supported, use 1min instead, request 20 days
      case '5min': return [20, 'day', 5]  // Request 20 days for multi-day view
      case '15min': return [20, 'day', 15]  // Request 20 days for multi-day view
      case '30min': return [20, 'day', 30]  // Request 20 days for multi-day view
      case '1hour': return [20, 'day', 60]
      case '1day': return [1, 'month', 1]
      default: return [20, 'day', 1]  // Default to 20 days for multi-day view
    }
  })()
  
  return fetchJSON(
    `${API_BASE}/charts/data/${symbol}?periodType=${periodType}&periodValue=${periodValue}&frequencyType=minute&frequency=${frequency}`
  )
}

export async function analyzeImage(file, imageUrl, symbol) {
  try {
    if (file) {
      // File upload using FormData
      const formData = new FormData()
      formData.append('file', file)
      if (symbol) {
        formData.append('symbol', symbol)
      }
      
      const response = await fetch(`${API_BASE}/vision/analyze`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || `HTTP error! status: ${response.status}`)
      }
      
      return await response.json()
    } else if (imageUrl) {
      // URL upload using JSON
      const response = await fetch(`${API_BASE}/vision/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          image_url: imageUrl,
          symbol: symbol || 'UNKNOWN'
        })
      })
      
      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || `HTTP error! status: ${response.status}`)
      }
      
      return await response.json()
    } else {
      throw new Error('Either file or imageUrl must be provided')
    }
  } catch (error) {
    console.error('Vision analysis error:', error)
    throw error
  }
}


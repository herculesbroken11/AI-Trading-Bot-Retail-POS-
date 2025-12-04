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


import React, { useState, useEffect } from 'react'
import Header from './components/Header'
import AutomationControl from './components/AutomationControl'
import AccountSummary from './components/AccountSummary'
import SystemHealth from './components/SystemHealth'
import PositionsTable from './components/PositionsTable'
import DailyReport from './components/DailyReport'
import TradesTable from './components/TradesTable'
import ComplianceMetrics from './components/ComplianceMetrics'
import OptimizationPanel from './components/OptimizationPanel'
import TradingActivityChart from './components/TradingActivityChart'
import RulesVerification from './components/RulesVerification'
import ActivityLog from './components/ActivityLog'
import MarketAnalysisStatus from './components/MarketAnalysisStatus'
import { getAccountId } from './services/api'

function App() {
  const [accountId, setAccountId] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)

  useEffect(() => {
    // Get account ID on mount
    getAccountId().then(id => {
      if (id) setAccountId(id)
    })

    // Auto-refresh every 30 seconds
    const interval = setInterval(() => {
      setLastUpdate(new Date())
    }, 30000)

    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    setLastUpdate(new Date())
  }

  return (
    <div className="app">
      <Header onRefresh={handleRefresh} />
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px', marginBottom: '20px' }}>
        <AutomationControl />
        <AccountSummary accountId={accountId} lastUpdate={lastUpdate} />
        <SystemHealth lastUpdate={lastUpdate} />
      </div>

      <PositionsTable lastUpdate={lastUpdate} />

      <DailyReport accountId={accountId} lastUpdate={lastUpdate} />

      <TradesTable accountId={accountId} lastUpdate={lastUpdate} />

      <ComplianceMetrics lastUpdate={lastUpdate} />

      <OptimizationPanel lastUpdate={lastUpdate} />

      <TradingActivityChart accountId={accountId} lastUpdate={lastUpdate} />

      <RulesVerification lastUpdate={lastUpdate} />

      <MarketAnalysisStatus lastUpdate={lastUpdate} />

      <ActivityLog lastUpdate={lastUpdate} />
    </div>
  )
}

export default App


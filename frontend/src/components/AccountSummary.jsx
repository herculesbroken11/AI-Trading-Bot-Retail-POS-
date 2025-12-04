import React, { useState, useEffect } from 'react'
import { getDailyReport } from '../services/api'
import './Card.css'

function AccountSummary({ accountId, lastUpdate }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (accountId) {
      loadData()
    }
  }, [accountId, lastUpdate])

  const loadData = async () => {
    try {
      const report = await getDailyReport(accountId)
      if (report) {
        setData(report.pnl || {})
      }
    } catch (error) {
      console.error('Failed to load account summary:', error)
    }
  }

  const pnlToday = data?.estimated_pnl || 0
  const pnlClass = pnlToday >= 0 ? 'positive' : 'negative'

  return (
    <div className="card">
      <h2>Account Summary</h2>
      <div className="metric">
        <span className="metric-label">Active Positions:</span>
        <span className="metric-value">-</span>
      </div>
      <div className="metric">
        <span className="metric-label">Today's Trades:</span>
        <span className="metric-value">{data?.total_trades || '-'}</span>
      </div>
      <div className="metric">
        <span className="metric-label">P&L Today:</span>
        <span className={`metric-value ${pnlClass}`}>
          {data ? `$${parseFloat(pnlToday).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` : '-'}
        </span>
      </div>
    </div>
  )
}

export default AccountSummary


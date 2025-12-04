import React, { useState, useEffect } from 'react'
import { getDailyReport } from '../services/api'
import './Card.css'

function DailyReport({ accountId, lastUpdate }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (accountId) {
      loadReport()
    }
  }, [accountId, lastUpdate])

  const loadReport = async () => {
    try {
      const report = await getDailyReport(accountId)
      setData(report)
    } catch (error) {
      console.error('Failed to load daily report:', error)
    }
  }

  if (!data) {
    return (
      <div className="card" style={{ gridColumn: '1 / -1', marginTop: '20px' }}>
        <h2>Daily Report & Audit</h2>
        <div style={{ textAlign: 'center', padding: '20px' }}>Loading...</div>
      </div>
    )
  }

  const pnl = data.pnl || {}

  return (
    <div className="card" style={{ gridColumn: '1 / -1', marginTop: '20px' }}>
      <h2>Daily Report & Audit</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px', marginTop: '15px' }}>
        <div className="metric">
          <span className="metric-label">Total Trades Today:</span>
          <span className="metric-value">{pnl.total_trades || 0}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Win Rate:</span>
          <span className="metric-value">
            {pnl.win_rate ? `${pnl.win_rate.toFixed(1)}%` : '0%'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Account Value:</span>
          <span className="metric-value">
            {pnl.account_value 
              ? `$${parseFloat(pnl.account_value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
              : '-'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Buying Power:</span>
          <span className="metric-value">
            {pnl.buying_power 
              ? `$${parseFloat(pnl.buying_power).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`
              : '-'}
          </span>
        </div>
      </div>
      <div style={{ marginTop: '20px' }}>
        <button className="btn" onClick={loadReport}>Refresh Report</button>
      </div>
      {data.ai_report && (
        <div style={{ marginTop: '20px', padding: '15px', background: '#2a2f4a', borderRadius: '5px' }}>
          <h3 style={{ color: '#667eea', marginBottom: '10px' }}>AI Analysis</h3>
          <div style={{ color: '#e0e0e0', whiteSpace: 'pre-wrap' }}>{data.ai_report}</div>
        </div>
      )}
    </div>
  )
}

export default DailyReport


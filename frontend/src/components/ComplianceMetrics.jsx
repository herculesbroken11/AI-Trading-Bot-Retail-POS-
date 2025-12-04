import React, { useState, useEffect } from 'react'
import { getComplianceReport } from '../services/api'
import './Card.css'

function ComplianceMetrics({ lastUpdate }) {
  const [metrics, setMetrics] = useState(null)

  useEffect(() => {
    loadMetrics()
  }, [lastUpdate])

  const loadMetrics = async () => {
    try {
      const today = new Date().toISOString().split('T')[0]
      const data = await getComplianceReport(today, today)
      if (data && data.metrics) {
        setMetrics(data.metrics)
      }
    } catch (error) {
      console.error('Failed to load compliance metrics:', error)
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Compliance & Audit Metrics</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginTop: '15px' }}>
        <div className="metric">
          <span className="metric-label">Total Volume:</span>
          <span className="metric-value">{metrics?.total_volume || 0}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Avg Trade Size:</span>
          <span className="metric-value">
            {metrics?.average_trade_size ? metrics.average_trade_size.toFixed(0) : 0}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Max Trade Size:</span>
          <span className="metric-value">{metrics?.max_trade_size || 0}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Risk Per Trade:</span>
          <span className="metric-value">{metrics?.risk_per_trade || '$300'}</span>
        </div>
      </div>
      <div style={{ marginTop: '20px' }}>
        <button className="btn" onClick={loadMetrics}>Refresh Metrics</button>
      </div>
    </div>
  )
}

export default ComplianceMetrics


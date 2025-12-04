import React from 'react'
import './Card.css'

function SystemHealth({ lastUpdate }) {
  return (
    <div className="card">
      <h2>System Health</h2>
      <div className="metric">
        <span className="metric-label">API Status:</span>
        <span className="metric-value">Connected</span>
      </div>
      <div className="metric">
        <span className="metric-label">Last Update:</span>
        <span className="metric-value">
          {lastUpdate ? lastUpdate.toLocaleTimeString() : '-'}
        </span>
      </div>
    </div>
  )
}

export default SystemHealth


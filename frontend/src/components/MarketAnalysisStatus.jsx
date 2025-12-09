import React, { useState, useEffect } from 'react'
import { getActivityLogs, getAutomationStatus } from '../services/api'
import './Card.css'

function MarketAnalysisStatus({ lastUpdate }) {
  const [recentActivity, setRecentActivity] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadStatus()
    // Poll every 5 seconds
    const interval = setInterval(loadStatus, 5000)
    return () => clearInterval(interval)
  }, [lastUpdate])

  const loadStatus = async () => {
    try {
      setLoading(true)
      const [activityData, automationData] = await Promise.all([
        getActivityLogs(20),
        getAutomationStatus()
      ])
      
      if (activityData && activityData.logs) {
        // Filter for analysis-related logs
        const analysisLogs = activityData.logs.filter(log => 
          log.message && (
            log.message.includes('Analyzing') ||
            log.message.includes('Setup detected') ||
            log.message.includes('4 Fantastics') ||
            log.message.includes('AI analysis') ||
            log.message.includes('Market analysis') ||
            log.message.includes('Chart generated') ||
            log.message.includes('vision analysis') ||
            log.message.includes('chart')
          )
        )
        setRecentActivity(analysisLogs.slice(0, 10))
      }
      
      if (automationData) {
        setStatus(automationData)
      }
    } catch (error) {
      console.error('Failed to load market analysis status:', error)
    } finally {
      setLoading(false)
    }
  }

  const getLogIcon = (type) => {
    switch (type) {
      case 'success': return '✓'
      case 'warning': return '⚠'
      case 'error': return '✗'
      case 'rule': return '📋'
      default: return 'ℹ'
    }
  }

  const getLogColor = (type) => {
    switch (type) {
      case 'success': return '#10b981'
      case 'warning': return '#f59e0b'
      case 'error': return '#ef4444'
      case 'rule': return '#667eea'
      default: return '#3b82f6'
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Live Market Analysis Status</h2>
      <p style={{ color: '#9ca3af', marginBottom: '20px', fontSize: '14px' }}>
        Real-time view of what the system is checking and analyzing right now. The AI uses chart images to visually verify OV trading rules.
      </p>

      {status && (
        <div style={{ marginBottom: '20px', padding: '15px', background: '#1f2937', borderRadius: '8px' }}>
          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
            <div>
              <span style={{ color: '#9ca3af' }}>Automation: </span>
              <span style={{ color: status.running ? '#10b981' : '#6b7280', fontWeight: 'bold' }}>
                {status.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div>
              <span style={{ color: '#9ca3af' }}>Market: </span>
              <span style={{ color: status.market_hours ? '#10b981' : '#6b7280', fontWeight: 'bold' }}>
                {status.market_hours ? 'Open' : 'Closed'}
              </span>
            </div>
            <div>
              <span style={{ color: '#9ca3af' }}>Watchlist: </span>
              <span style={{ color: '#e5e7eb', fontWeight: 'bold' }}>
                {status.watchlist ? status.watchlist.length : 0} symbols
              </span>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: '15px' }}>
        <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Recent Analysis Activity</h3>
        <div
          style={{
            background: '#111827',
            borderRadius: '8px',
            padding: '15px',
            maxHeight: '300px',
            overflowY: 'auto',
            fontFamily: 'monospace',
            fontSize: '12px'
          }}
        >
          {recentActivity.length === 0 ? (
            <div style={{ color: '#9ca3af', textAlign: 'center', padding: '20px' }}>
              {status && status.running ? (
                <div>
                  <p>Waiting for market analysis to start...</p>
                  <p style={{ fontSize: '11px', marginTop: '10px' }}>
                    The system analyzes symbols every 5 minutes during market hours.
                  </p>
                </div>
              ) : (
                <div>
                  <p>Automation is not running.</p>
                  <p style={{ fontSize: '11px', marginTop: '10px' }}>
                    Start automation to see live market analysis.
                  </p>
                </div>
              )}
            </div>
          ) : (
            recentActivity.map((log, idx) => (
              <div
                key={idx}
                style={{
                  padding: '8px',
                  marginBottom: '6px',
                  background: '#1f2937',
                  borderRadius: '4px',
                  borderLeft: `3px solid ${getLogColor(log.type)}`
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ color: getLogColor(log.type), fontWeight: 'bold' }}>
                    {getLogIcon(log.type)}
                  </span>
                  <span style={{ color: '#9ca3af', fontSize: '11px' }}>{log.time}</span>
                  {log.symbol && (
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: '#667eea20',
                        color: '#667eea',
                        fontSize: '10px',
                        fontWeight: 'bold'
                      }}
                    >
                      {log.symbol}
                    </span>
                  )}
                  {log.rule && (
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: '#10b98120',
                        color: '#10b981',
                        fontSize: '10px'
                      }}
                    >
                      {log.rule}
                    </span>
                  )}
                </div>
                <div style={{ color: '#e5e7eb', marginLeft: '20px' }}>{log.message}</div>
              </div>
            ))
          )}
        </div>
      </div>

      <div style={{ marginTop: '15px' }}>
        <button className="btn" onClick={loadStatus} disabled={loading}>
          Refresh Status
        </button>
      </div>

      {status && status.running && recentActivity.length === 0 && (
        <div style={{ marginTop: '15px', padding: '10px', background: '#1f2937', borderRadius: '6px', fontSize: '12px', color: '#9ca3af' }}>
          <strong>Note:</strong> The system analyzes your watchlist every 5 minutes. If no setups are found, you'll see "No setup detected" messages. Trades only execute when:
          <ul style={{ marginTop: '8px', paddingLeft: '20px' }}>
            <li>An OV setup is detected (Whale, Kamikaze, RBI, GBI, etc.)</li>
            <li>All 4 Fantastics conditions are met</li>
            <li>Chart is generated and analyzed by AI vision</li>
            <li>AI confirms with confidence &gt; 70% (using both data and visual chart analysis)</li>
          </ul>
        </div>
      )}
    </div>
  )
}

export default MarketAnalysisStatus


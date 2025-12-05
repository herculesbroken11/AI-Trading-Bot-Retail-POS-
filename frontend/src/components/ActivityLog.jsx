import React, { useState, useEffect } from 'react'
import { getActivityLogs } from '../services/api'
import './Card.css'

function ActivityLog({ lastUpdate }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadLogs()
    // Poll for new logs every 5 seconds
    const interval = setInterval(loadLogs, 5000)
    return () => clearInterval(interval)
  }, [lastUpdate])

  const loadLogs = async () => {
    try {
      setLoading(true)
      const data = await getActivityLogs(50)
      if (data && data.logs) {
        setLogs(data.logs.reverse()) // Reverse to show newest first
      }
    } catch (error) {
      console.error('Failed to load activity logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const addLog = (type, message, rule) => {
    const newLog = {
      time: new Date().toLocaleTimeString(),
      type,
      message,
      rule
    }
    setLogs(prev => [newLog, ...prev].slice(0, 50)) // Keep last 50 logs
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

  const getLogIcon = (type) => {
    switch (type) {
      case 'success': return '✓'
      case 'warning': return '⚠'
      case 'error': return '✗'
      case 'rule': return '📋'
      default: return 'ℹ'
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Real-Time Activity Log</h2>
      <p style={{ color: '#9ca3af', marginBottom: '20px', fontSize: '14px' }}>
        This log shows real-time activity of the trading system, including rule checks, signal generation, and trade execution.
      </p>

      <div
        style={{
          background: '#111827',
          borderRadius: '8px',
          padding: '15px',
          maxHeight: '400px',
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: '13px'
        }}
      >
        {logs.length === 0 ? (
          <div style={{ color: '#9ca3af', textAlign: 'center', padding: '20px' }}>
            No activity logged yet. Activity will appear here once the system starts running.
          </div>
        ) : (
          logs.map((log, idx) => (
            <div
              key={idx}
              style={{
                padding: '10px',
                marginBottom: '8px',
                background: '#1f2937',
                borderRadius: '4px',
                borderLeft: `3px solid ${getLogColor(log.type)}`
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '5px' }}>
                <span
                  style={{
                    color: getLogColor(log.type),
                    fontWeight: 'bold',
                    fontSize: '14px'
                  }}
                >
                  {getLogIcon(log.type)}
                </span>
                <span style={{ color: '#9ca3af', fontSize: '11px' }}>{log.time}</span>
                {log.rule && (
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: '#667eea20',
                      color: '#667eea',
                      fontSize: '10px'
                    }}
                  >
                    {log.rule}
                  </span>
                )}
              </div>
              <div style={{ color: '#e5e7eb', marginLeft: '24px' }}>{log.message}</div>
            </div>
          ))
        )}
      </div>

      <div style={{ marginTop: '15px' }}>
        <button className="btn" onClick={loadLogs} disabled={loading}>
          Refresh Logs
        </button>
      </div>

      <div style={{ marginTop: '15px', padding: '10px', background: '#1f2937', borderRadius: '6px', fontSize: '12px', color: '#9ca3af' }}>
        <strong>Note:</strong> This log shows real-time system activity including rule checks, signal generation, and trade execution. Logs are automatically refreshed every 5 seconds.
      </div>
    </div>
  )
}

export default ActivityLog


import React, { useState, useEffect } from 'react'
import { getRulesStatus } from '../services/api'
import './Card.css'

function RulesVerification({ lastUpdate }) {
  const [rules, setRules] = useState([])
  const [automationRunning, setAutomationRunning] = useState(false)
  const [marketHours, setMarketHours] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadRulesStatus()
    // Refresh every 10 seconds
    const interval = setInterval(loadRulesStatus, 10000)
    return () => clearInterval(interval)
  }, [lastUpdate])

  const loadRulesStatus = async () => {
    try {
      setLoading(true)
      const data = await getRulesStatus()
      if (data) {
        setRules(data.rules || [])
        setAutomationRunning(data.automation_running || false)
        setMarketHours(data.market_hours || false)
      }
    } catch (error) {
      console.error('Failed to load rules status:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#10b981' // green
      case 'monitoring': return '#3b82f6' // blue
      case 'pending': return '#f59e0b' // yellow
      case 'idle': return '#6b7280' // gray
      default: return '#9ca3af' // light gray
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'active': return 'Active'
      case 'monitoring': return 'Monitoring'
      case 'pending': return 'Pending'
      case 'idle': return 'Idle'
      default: return 'Unknown'
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>OV Trading Rules Verification</h2>
      <p style={{ color: '#9ca3af', marginBottom: '20px', fontSize: '14px' }}>
        This panel shows which Oliver Vélez trading rules are currently active and being enforced by the system.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '15px' }}>
        {rules.map((rule, idx) => (
          <div
            key={idx}
            style={{
              padding: '15px',
              background: '#1f2937',
              borderRadius: '8px',
              border: `2px solid ${getStatusColor(rule.status)}`,
              borderLeft: `4px solid ${getStatusColor(rule.status)}`
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h3 style={{ color: '#e5e7eb', margin: 0, fontSize: '16px' }}>{rule.name}</h3>
              <span
                style={{
                  padding: '4px 12px',
                  borderRadius: '12px',
                  background: getStatusColor(rule.status) + '20',
                  color: getStatusColor(rule.status),
                  fontSize: '12px',
                  fontWeight: 'bold'
                }}
              >
                {getStatusText(rule.status)}
              </span>
            </div>
            <p style={{ color: '#9ca3af', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
              {rule.description}
            </p>
          </div>
        ))}
      </div>

      <div style={{ marginTop: '20px', padding: '15px', background: '#1f2937', borderRadius: '8px' }}>
        <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Rule Status Legend</h3>
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#10b981' }}></div>
            <span style={{ color: '#e5e7eb', fontSize: '13px' }}>Active - Rule is currently being enforced</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#3b82f6' }}></div>
            <span style={{ color: '#e5e7eb', fontSize: '13px' }}>Monitoring - System is checking for this rule</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#f59e0b' }}></div>
            <span style={{ color: '#e5e7eb', fontSize: '13px' }}>Pending - Rule will activate when conditions are met</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#6b7280' }}></div>
            <span style={{ color: '#e5e7eb', fontSize: '13px' }}>Idle - Automation not running</span>
          </div>
        </div>
      </div>

      <div style={{ marginTop: '20px', display: 'flex', gap: '10px', alignItems: 'center' }}>
        <button className="btn" onClick={loadRulesStatus} disabled={loading}>
          Refresh Rules Status
        </button>
        <div style={{ fontSize: '13px', color: '#9ca3af' }}>
          Automation: <span style={{ color: automationRunning ? '#10b981' : '#6b7280' }}>
            {automationRunning ? 'Running' : 'Stopped'}
          </span> | 
          Market: <span style={{ color: marketHours ? '#10b981' : '#6b7280' }}>
            {marketHours ? 'Open' : 'Closed'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default RulesVerification


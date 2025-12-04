import React, { useState, useEffect } from 'react'
import { getAutomationStatus, startAutomation, stopAutomation } from '../services/api'
import './Card.css'

function AutomationControl() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    try {
      const data = await getAutomationStatus()
      setStatus(data)
    } catch (error) {
      console.error('Failed to load automation status:', error)
    }
  }

  const handleStart = async () => {
    setLoading(true)
    try {
      await startAutomation()
      await loadStatus()
      alert('Automation started')
    } catch (error) {
      alert('Failed to start automation')
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    if (!window.confirm('Are you sure you want to stop automation?')) return
    
    setLoading(true)
    try {
      await stopAutomation()
      await loadStatus()
      alert('Automation stopped')
    } catch (error) {
      alert('Failed to stop automation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Automation Control</h2>
      <div className="metric">
        <span className="metric-label">Status:</span>
        <span className="metric-value">
          {status?.running ? 'Running' : status ? 'Stopped' : '-'}
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Market Hours:</span>
        <span className="metric-value">
          {status?.market_hours ? 'Open' : status ? 'Closed' : '-'}
        </span>
      </div>
      <div className="metric">
        <span className="metric-label">Watchlist:</span>
        <span className="metric-value">
          {status?.watchlist ? status.watchlist.length : '-'}
        </span>
      </div>
      <div style={{ marginTop: '15px' }}>
        <button 
          className="btn" 
          onClick={handleStart} 
          disabled={loading || status?.running}
        >
          Start
        </button>
        <button 
          className="btn danger" 
          onClick={handleStop} 
          disabled={loading || !status?.running}
        >
          Stop
        </button>
      </div>
    </div>
  )
}

export default AutomationControl


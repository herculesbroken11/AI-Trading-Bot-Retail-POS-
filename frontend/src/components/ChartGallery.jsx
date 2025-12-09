import React, { useState, useEffect } from 'react'
import { getRecentCharts } from '../services/api'
import './Card.css'

function ChartGallery({ lastUpdate }) {
  const [charts, setCharts] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedChart, setSelectedChart] = useState(null)

  useEffect(() => {
    loadCharts()
    // Poll every 10 seconds for new charts
    const interval = setInterval(loadCharts, 10000)
    return () => clearInterval(interval)
  }, [lastUpdate])

  const loadCharts = async () => {
    try {
      setLoading(true)
      const data = await getRecentCharts(10)
      if (data && data.charts) {
        setCharts(data.charts)
      }
    } catch (error) {
      console.error('Failed to load charts:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatTime = (timestamp) => {
    try {
      const dt = new Date(timestamp)
      return dt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    } catch {
      return timestamp
    }
  }

  const getActionColor = (action) => {
    switch (action) {
      case 'BUY': return '#10b981'
      case 'SELL': return '#ef4444'
      case 'SHORT': return '#f59e0b'
      default: return '#6b7280'
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>AI Chart Analysis Gallery</h2>
      <p style={{ color: '#9ca3af', marginBottom: '20px', fontSize: '14px' }}>
        Recent charts analyzed by AI vision. Click to view full size.
      </p>

      {loading && charts.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
          Loading charts...
        </div>
      )}

      {!loading && charts.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
          <p>No charts analyzed yet.</p>
          <p style={{ fontSize: '12px', marginTop: '10px' }}>
            Charts will appear here when the bot analyzes symbols during market hours.
          </p>
        </div>
      )}

      {charts.length > 0 && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', 
          gap: '15px',
          marginBottom: '20px'
        }}>
          {charts.map((chart, idx) => (
            <div
              key={idx}
              onClick={() => setSelectedChart(chart)}
              style={{
                background: '#1f2937',
                borderRadius: '8px',
                padding: '12px',
                cursor: 'pointer',
                border: '1px solid #374151',
                transition: 'all 0.2s',
                position: 'relative'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#667eea'
                e.currentTarget.style.transform = 'translateY(-2px)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#374151'
                e.currentTarget.style.transform = 'translateY(0)'
              }}
            >
              <div style={{ marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ 
                  fontWeight: 'bold', 
                  color: '#e5e7eb',
                  fontSize: '16px'
                }}>
                  {chart.symbol}
                </span>
                {chart.ai_action && (
                  <span style={{
                    padding: '4px 8px',
                    borderRadius: '4px',
                    background: `${getActionColor(chart.ai_action)}20`,
                    color: getActionColor(chart.ai_action),
                    fontSize: '11px',
                    fontWeight: 'bold'
                  }}>
                    {chart.ai_action}
                  </span>
                )}
              </div>

              {chart.setup_type && (
                <div style={{ marginBottom: '8px' }}>
                  <span style={{ 
                    fontSize: '12px', 
                    color: '#9ca3af',
                    padding: '2px 6px',
                    background: '#374151',
                    borderRadius: '4px'
                  }}>
                    {chart.setup_type}
                  </span>
                </div>
              )}

              <div style={{ 
                width: '100%', 
                height: '180px', 
                background: '#111827',
                borderRadius: '6px',
                overflow: 'hidden',
                marginBottom: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <img
                  src={`data:image/png;base64,${chart.chart_image}`}
                  alt={`${chart.symbol} chart`}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: '#9ca3af' }}>
                <span>{formatTime(chart.timestamp)}</span>
                {chart.ai_confidence !== null && chart.ai_confidence !== undefined && (
                  <span style={{ color: chart.ai_confidence > 0.7 ? '#10b981' : '#f59e0b' }}>
                    {Math.round(chart.ai_confidence * 100)}% confidence
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedChart && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.9)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            cursor: 'pointer'
          }}
          onClick={() => setSelectedChart(null)}
        >
          <div style={{ 
            maxWidth: '90%', 
            maxHeight: '90%',
            position: 'relative',
            background: '#1f2937',
            borderRadius: '8px',
            padding: '20px'
          }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              marginBottom: '15px'
            }}>
              <h3 style={{ color: '#e5e7eb', margin: 0 }}>
                {selectedChart.symbol} - {selectedChart.setup_type || 'Chart Analysis'}
              </h3>
              <button
                onClick={() => setSelectedChart(null)}
                style={{
                  background: '#ef4444',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '8px 16px',
                  cursor: 'pointer',
                  fontSize: '14px'
                }}
              >
                Close
              </button>
            </div>
            <img
              src={`data:image/png;base64,${selectedChart.chart_image}`}
              alt={`${selectedChart.symbol} full chart`}
              style={{
                maxWidth: '100%',
                maxHeight: 'calc(90vh - 100px)',
                objectFit: 'contain'
              }}
              onClick={(e) => e.stopPropagation()}
            />
            <div style={{ marginTop: '15px', color: '#9ca3af', fontSize: '12px' }}>
              <div>Time: {formatTime(selectedChart.timestamp)}</div>
              {selectedChart.ai_action && (
                <div>AI Action: <span style={{ color: getActionColor(selectedChart.ai_action) }}>{selectedChart.ai_action}</span></div>
              )}
              {selectedChart.ai_confidence !== null && selectedChart.ai_confidence !== undefined && (
                <div>Confidence: {Math.round(selectedChart.ai_confidence * 100)}%</div>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: '15px' }}>
        <button className="btn" onClick={loadCharts} disabled={loading}>
          Refresh Charts
        </button>
      </div>
    </div>
  )
}

export default ChartGallery


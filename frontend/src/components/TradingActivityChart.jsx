import React, { useState, useEffect } from 'react'
import { getDailyReport, getPositions } from '../services/api'
import './Card.css'

function TradingActivityChart({ accountId, lastUpdate }) {
  const [trades, setTrades] = useState([])
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [accountId, lastUpdate])

  const loadData = async () => {
    try {
      setLoading(true)
      const [reportData, positionsData] = await Promise.all([
        accountId ? getDailyReport(accountId) : null,
        getPositions()
      ])
      
      if (reportData && reportData.trades) {
        setTrades(reportData.trades)
      }
      if (positionsData) {
        setPositions(Array.isArray(positionsData) ? positionsData : [])
      }
    } catch (error) {
      console.error('Failed to load trading activity:', error)
    } finally {
      setLoading(false)
    }
  }

  // Calculate P&L chart data
  const calculateChartData = () => {
    if (!trades || trades.length === 0) {
      return { labels: [], data: [], cumulative: [] }
    }

    const sortedTrades = [...trades].sort((a, b) => {
      const dateA = new Date(a.entry_time || a.time || 0)
      const dateB = new Date(b.entry_time || b.time || 0)
      return dateA - dateB
    })

    const labels = sortedTrades.map(t => {
      const date = new Date(t.entry_time || t.time)
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    })

    const data = sortedTrades.map(t => parseFloat(t.pnl || t.profit || 0))
    const cumulative = data.reduce((acc, val, idx) => {
      acc.push((acc[idx - 1] || 0) + val)
      return acc
    }, [])

    return { labels, data, cumulative }
  }

  const { labels, data, cumulative } = calculateChartData()
  const maxValue = Math.max(...cumulative, 0, ...data.map(Math.abs))
  const minValue = Math.min(...cumulative, 0, ...data.map(Math.abs))

  const renderChart = () => {
    if (labels.length === 0) {
      return (
        <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
          No trading activity yet. Trades will appear here once the system starts trading.
        </div>
      )
    }

    const chartHeight = 200
    const chartWidth = Math.max(600, labels.length * 80)
    const padding = 40

    return (
      <div style={{ overflowX: 'auto', padding: '20px' }}>
        <svg width={chartWidth} height={chartHeight + padding * 2} style={{ minWidth: '100%' }}>
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map(ratio => {
            const y = padding + (chartHeight * (1 - ratio))
            const value = minValue + (maxValue - minValue) * ratio
            return (
              <g key={ratio}>
                <line
                  x1={padding}
                  y1={y}
                  x2={chartWidth - padding}
                  y2={y}
                  stroke="#374151"
                  strokeWidth="1"
                  strokeDasharray="4,4"
                />
                <text
                  x={padding - 10}
                  y={y + 4}
                  fill="#9ca3af"
                  fontSize="10"
                  textAnchor="end"
                >
                  ${value.toFixed(0)}
                </text>
              </g>
            )
          })}

          {/* Zero line */}
          <line
            x1={padding}
            y1={padding + chartHeight / 2}
            x2={chartWidth - padding}
            y2={padding + chartHeight / 2}
            stroke="#6b7280"
            strokeWidth="1"
          />

          {/* Cumulative P&L line */}
          {cumulative.length > 1 && cumulative.map((value, idx) => {
            if (idx === 0) return null
            const x1 = padding + ((idx - 1) / (labels.length - 1)) * (chartWidth - padding * 2)
            const y1 = padding + chartHeight - ((cumulative[idx - 1] - minValue) / (maxValue - minValue || 1)) * chartHeight
            const x2 = padding + (idx / (labels.length - 1)) * (chartWidth - padding * 2)
            const y2 = padding + chartHeight - ((value - minValue) / (maxValue - minValue || 1)) * chartHeight
            
            return (
              <line
                key={idx}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={value >= 0 ? "#10b981" : "#ef4444"}
                strokeWidth="2"
              />
            )
          })}

          {/* Data points */}
          {cumulative.map((value, idx) => {
            const x = padding + (idx / (labels.length - 1 || 1)) * (chartWidth - padding * 2)
            const y = padding + chartHeight - ((value - minValue) / (maxValue - minValue || 1)) * chartHeight
            
            return (
              <circle
                key={idx}
                cx={x}
                cy={y}
                r="4"
                fill={value >= 0 ? "#10b981" : "#ef4444"}
                stroke="#1f2937"
                strokeWidth="1"
              />
            )
          })}

          {/* X-axis labels */}
          {labels.map((label, idx) => {
            if (idx % Math.ceil(labels.length / 8) !== 0 && idx !== labels.length - 1) return null
            const x = padding + (idx / (labels.length - 1 || 1)) * (chartWidth - padding * 2)
            return (
              <text
                key={idx}
                x={x}
                y={chartHeight + padding + 15}
                fill="#9ca3af"
                fontSize="9"
                textAnchor="middle"
                transform={`rotate(-45 ${x} ${chartHeight + padding + 15})`}
              >
                {label}
              </text>
            )
          })}
        </svg>
      </div>
    )
  }

  const totalPnL = cumulative.length > 0 ? cumulative[cumulative.length - 1] : 0
  const winCount = data.filter(d => d > 0).length
  const lossCount = data.filter(d => d < 0).length
  const winRate = data.length > 0 ? ((winCount / data.length) * 100).toFixed(1) : 0

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Trading Activity Chart</h2>
      
      <div style={{ display: 'flex', gap: '20px', marginBottom: '20px', flexWrap: 'wrap' }}>
        <div className="metric">
          <span className="metric-label">Total Trades:</span>
          <span className="metric-value">{trades.length || positions.length}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Total P&L:</span>
          <span className={`metric-value ${totalPnL >= 0 ? 'positive' : 'negative'}`}>
            ${totalPnL.toFixed(2)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Win Rate:</span>
          <span className={`metric-value ${winRate >= 50 ? 'positive' : 'negative'}`}>
            {winRate}%
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Wins:</span>
          <span className="metric-value positive">{winCount}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Losses:</span>
          <span className="metric-value negative">{lossCount}</span>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px' }}>Loading chart data...</div>
      ) : (
        renderChart()
      )}

      <div style={{ marginTop: '20px' }}>
        <button className="btn" onClick={loadData} disabled={loading}>
          Refresh Chart
        </button>
      </div>

      {positions.length > 0 && (
        <div style={{ marginTop: '20px', padding: '15px', background: '#1f2937', borderRadius: '8px' }}>
          <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Active Positions</h3>
          {positions.map((pos, idx) => (
            <div key={idx} style={{ marginBottom: '10px', padding: '10px', background: '#111827', borderRadius: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#e5e7eb', fontWeight: 'bold' }}>{pos.symbol}</span>
                <span style={{ color: pos.pnl >= 0 ? '#10b981' : '#ef4444' }}>
                  P&L: ${(pos.pnl || 0).toFixed(2)}
                </span>
              </div>
              <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '5px' }}>
                {pos.quantity} shares @ ${(pos.entry_price || 0).toFixed(2)} | 
                Direction: {pos.direction || 'LONG'} | 
                Setup: {pos.setup_type || 'N/A'}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default TradingActivityChart


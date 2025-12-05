import React, { useState, useEffect } from 'react'
import { getPerformanceAnalysis, getSetupWeights, getOptimizedParameters, getOptimizationSummary, adjustSetupWeights, optimizeParameters } from '../services/api'
import './Card.css'

function OptimizationPanel({ lastUpdate }) {
  const [summary, setSummary] = useState(null)
  const [performance, setPerformance] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [lastUpdate])

  const loadData = async () => {
    try {
      setLoading(true)
      const [summaryData, perfData] = await Promise.all([
        getOptimizationSummary(),
        getPerformanceAnalysis(30)
      ])
      setSummary(summaryData)
      setPerformance(perfData)
    } catch (error) {
      console.error('Failed to load optimization data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAdjustWeights = async () => {
    try {
      setLoading(true)
      await adjustSetupWeights(10)
      await loadData()
      alert('Setup weights adjusted successfully')
    } catch (error) {
      alert('Failed to adjust weights')
    } finally {
      setLoading(false)
    }
  }

  const handleOptimizeParameters = async () => {
    try {
      setLoading(true)
      await optimizeParameters()
      await loadData()
      alert('Parameters optimized successfully')
    } catch (error) {
      alert('Failed to optimize parameters')
    } finally {
      setLoading(false)
    }
  }

  if (loading && !summary) {
    return (
      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Optimization & Performance</h2>
        <div style={{ textAlign: 'center', padding: '20px' }}>Loading...</div>
      </div>
    )
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Optimization & Performance</h2>
      
      {performance && (
        <div style={{ marginTop: '15px' }}>
          <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Performance Analysis (Last 30 Days)</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
            <div className="metric">
              <span className="metric-label">Total Trades:</span>
              <span className="metric-value">{performance.total_trades || 0}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Win Rate:</span>
              <span className={`metric-value ${performance.win_rate >= 50 ? 'positive' : 'negative'}`}>
                {performance.win_rate ? `${performance.win_rate.toFixed(1)}%` : '0%'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Total P&L:</span>
              <span className={`metric-value ${performance.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                ${performance.total_pnl ? performance.total_pnl.toFixed(2) : '0.00'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Avg Win:</span>
              <span className="metric-value positive">
                ${performance.avg_win ? performance.avg_win.toFixed(2) : '0.00'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Avg Loss:</span>
              <span className="metric-value negative">
                ${performance.avg_loss ? Math.abs(performance.avg_loss).toFixed(2) : '0.00'}
              </span>
            </div>
          </div>
        </div>
      )}

      {summary && summary.setup_weights && (
        <div style={{ marginTop: '20px' }}>
          <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Setup Weights</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
            {Object.entries(summary.setup_weights).map(([setup, weight]) => (
              <div key={setup} className="metric">
                <span className="metric-label">{setup.toUpperCase()}:</span>
                <span className="metric-value">{weight.toFixed(2)}</span>
              </div>
            ))}
          </div>
          <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '10px' }}>
            Higher weight = more likely to trade this setup type
          </p>
        </div>
      )}

      {summary && summary.optimized_parameters && (
        <div style={{ marginTop: '20px' }}>
          <h3 style={{ color: '#667eea', marginBottom: '10px' }}>Optimized Parameters</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
            <div className="metric">
              <span className="metric-label">Stop Distance (ATR):</span>
              <span className="metric-value">{summary.optimized_parameters.stop_distance_atr || '1.5'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Target Distance (ATR):</span>
              <span className="metric-value">{summary.optimized_parameters.target_distance_atr || '3.0'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Trailing Stop (ATR):</span>
              <span className="metric-value">{summary.optimized_parameters.trailing_stop_atr || '0.5'}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Volatility Adjustment:</span>
              <span className="metric-value">{summary.optimized_parameters.volatility_adjustment || '1.0'}</span>
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
        <button className="btn" onClick={handleAdjustWeights} disabled={loading}>
          Adjust Setup Weights
        </button>
        <button className="btn" onClick={handleOptimizeParameters} disabled={loading}>
          Optimize Parameters
        </button>
        <button className="btn" onClick={loadData} disabled={loading}>
          Refresh
        </button>
      </div>

      {summary && summary.last_optimization && (
        <p style={{ fontSize: '12px', color: '#9ca3af', marginTop: '10px' }}>
          Last optimization: {new Date(summary.last_optimization).toLocaleString()}
        </p>
      )}
    </div>
  )
}

export default OptimizationPanel


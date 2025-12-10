import React, { useState, useEffect } from 'react'
import RealTimeChart from './RealTimeChart'
import { getWatchlist } from '../services/api'
import './Card.css'

function MultiChartView({ lastUpdate }) {
  const [watchlist, setWatchlist] = useState([])
  const [timeframe, setTimeframe] = useState('2min')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadWatchlist()
  }, [])

  const loadWatchlist = async () => {
    try {
      const watchlistData = await getWatchlist()
      if (watchlistData && watchlistData.watchlist && watchlistData.watchlist.length > 0) {
        setWatchlist(watchlistData.watchlist)
      }
    } catch (error) {
      console.error('Failed to load watchlist:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <h2>Multi-Chart View</h2>
        <p style={{ color: '#9ca3af', textAlign: 'center', padding: '20px' }}>
          Loading watchlist...
        </p>
      </div>
    )
  }

  if (watchlist.length === 0) {
    return (
      <div className="card">
        <h2>Multi-Chart View</h2>
        <p style={{ color: '#9ca3af', textAlign: 'center', padding: '20px' }}>
          No symbols in watchlist. Please set TRADING_WATCHLIST in .env file.
        </p>
      </div>
    )
  }

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
        <h2 style={{ margin: 0 }}>Multi-Chart View ({watchlist.length} symbols)</h2>
        <select
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
          style={{
            padding: '8px 12px',
            background: '#2a2f4a',
            border: '1px solid #2a2f4a',
            borderRadius: '5px',
            color: '#e0e0e0',
            fontSize: '14px'
          }}
          >
          <option value="2min">2 Min</option>
          <option value="5min">5 Min</option>
          <option value="15min">15 Min</option>
        </select>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))',
        gap: '20px'
      }}>
        {watchlist.map(symbol => (
          <div key={symbol}>
            <RealTimeChart 
              symbol={symbol} 
              lastUpdate={lastUpdate}
              timeframe={timeframe}
              compact={true}
            />
          </div>
        ))}
      </div>
    </div>
  )
}

export default MultiChartView


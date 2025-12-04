import React, { useState, useEffect } from 'react'
import { getDailyReport } from '../services/api'
import './Card.css'
import './Table.css'

function TradesTable({ accountId, lastUpdate }) {
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (accountId) {
      loadTrades()
    }
  }, [accountId, lastUpdate])

  const loadTrades = async () => {
    try {
      setLoading(true)
      const report = await getDailyReport(accountId)
      if (report && report.trades) {
        setTrades(report.trades)
      }
    } catch (error) {
      console.error('Failed to load trades:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: '20px' }}>
      <h2>Today's Trades</h2>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>Loading...</div>
      ) : trades.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>No trades today</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Action</th>
              <th>Quantity</th>
              <th>Price</th>
              <th>Setup</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, idx) => {
              const timestamp = new Date(trade.timestamp || trade.timestamp)
              const timeStr = timestamp.toLocaleTimeString()
              
              return (
                <tr key={idx}>
                  <td>{timeStr}</td>
                  <td>{trade.symbol || '-'}</td>
                  <td>{trade.action || '-'}</td>
                  <td>{trade.quantity || '-'}</td>
                  <td>${trade.price ? parseFloat(trade.price).toFixed(2) : '-'}</td>
                  <td>{trade.setup_type || '-'}</td>
                  <td>{trade.status || '-'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default TradesTable


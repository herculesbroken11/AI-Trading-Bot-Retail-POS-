import React, { useState, useEffect } from 'react'
import { getPositions } from '../services/api'
import './Card.css'
import './Table.css'

function PositionsTable({ lastUpdate }) {
  const [positions, setPositions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPositions()
  }, [lastUpdate])

  const loadPositions = async () => {
    try {
      setLoading(true)
      const data = await getPositions()
      if (data && data.positions) {
        setPositions(data.positions)
      }
    } catch (error) {
      console.error('Failed to load positions:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>Active Positions</h2>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>Loading...</div>
      ) : positions.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '20px' }}>No active positions</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Direction</th>
              <th>Entry</th>
              <th>Current</th>
              <th>Stop</th>
              <th>P&L</th>
              <th>Setup</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((pos, idx) => {
              const pnl = pos.current_price 
                ? ((pos.current_price - pos.entry_price) * pos.quantity * (pos.direction === 'LONG' ? 1 : -1)).toFixed(2)
                : '-'
              const pnlClass = pnl !== '-' ? (parseFloat(pnl) >= 0 ? 'positive' : 'negative') : ''
              
              return (
                <tr key={idx}>
                  <td>{pos.symbol}</td>
                  <td>{pos.direction}</td>
                  <td>${pos.entry_price?.toFixed(2) || '-'}</td>
                  <td>${pos.current_price?.toFixed(2) || '-'}</td>
                  <td>${pos.current_stop?.toFixed(2) || pos.stop_loss?.toFixed(2) || '-'}</td>
                  <td className={pnlClass}>${pnl}</td>
                  <td>{pos.setup_type || '-'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default PositionsTable


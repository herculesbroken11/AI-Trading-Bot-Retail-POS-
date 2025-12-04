import React from 'react'
import './Header.css'

function Header({ onRefresh }) {
  return (
    <header className="header">
      <div className="header-content">
        <h1>Oliver Vélez Trading System</h1>
        <button className="btn refresh-btn" onClick={onRefresh}>
          Refresh
        </button>
      </div>
    </header>
  )
}

export default Header


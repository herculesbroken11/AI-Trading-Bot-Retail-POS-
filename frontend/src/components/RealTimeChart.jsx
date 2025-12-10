import React, { useState, useEffect } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { Line, Bar } from 'react-chartjs-2'
import { getWatchlist } from '../services/api'
import './Card.css'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

function RealTimeChart({ symbol: propSymbol, lastUpdate, timeframe: propTimeframe, compact = false }) {
  const [chartData, setChartData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [timeframe, setTimeframe] = useState(propTimeframe || '2min')
  const [selectedSymbol, setSelectedSymbol] = useState(propSymbol || '')
  const [watchlist, setWatchlist] = useState([])
  const [showIndicators, setShowIndicators] = useState({
    mm8: true,
    mm20: true,
    mm200: true,
    volume: true
  })

  useEffect(() => {
    // Load watchlist from automation status
    loadWatchlist()
  }, [])

  useEffect(() => {
    // Update selected symbol if prop changes
    if (propSymbol && propSymbol !== selectedSymbol) {
      setSelectedSymbol(propSymbol)
    }
  }, [propSymbol])

  useEffect(() => {
    if (propTimeframe && propTimeframe !== timeframe) {
      setTimeframe(propTimeframe)
    }
  }, [propTimeframe])

  useEffect(() => {
    if (selectedSymbol) {
      loadChartData()
    }
  }, [selectedSymbol, timeframe, lastUpdate])

  const loadWatchlist = async () => {
    try {
      // Get watchlist from charts endpoint (reads TRADING_WATCHLIST env)
      const watchlistData = await getWatchlist()
      if (watchlistData && watchlistData.watchlist && watchlistData.watchlist.length > 0) {
        console.log('Loaded watchlist from TRADING_WATCHLIST:', watchlistData.watchlist)
        setWatchlist(watchlistData.watchlist)
        // Set first symbol from watchlist if no symbol provided
        if (!propSymbol && watchlistData.watchlist.length > 0) {
          setSelectedSymbol(watchlistData.watchlist[0])
        }
      } else {
        console.error('TRADING_WATCHLIST is empty or not configured. Please set TRADING_WATCHLIST in .env file.')
        setError('No watchlist configured. Please set TRADING_WATCHLIST in .env file.')
        setWatchlist([])
      }
    } catch (error) {
      console.error('Failed to load watchlist from /charts/watchlist:', error)
      setError(`Failed to load watchlist: ${error.message}. Please ensure TRADING_WATCHLIST is set in .env file.`)
      setWatchlist([])
    }
  }

  const loadChartData = async () => {
    if (!selectedSymbol) return
    
    setLoading(true)
    setError(null)
    
    try {
      // Parse timeframe
      const [periodValue, periodType, frequency] = parseTimeframe(timeframe)
      
      const response = await fetch(
        `${window.location.origin}/charts/data/${selectedSymbol}?periodType=${periodType}&periodValue=${periodValue}&frequencyType=minute&frequency=${frequency}`
      )
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      setChartData(data)
    } catch (err) {
      console.error('Failed to load chart data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const parseTimeframe = (tf) => {
    // Returns [periodValue, periodType, frequency]
    // Note: Schwab API only accepts [1, 5, 10, 15, 30] for minute frequency
    switch (tf) {
      case '1min':
        return [1, 'day', 1]
      case '2min':
        // 2min not supported, use 1min instead
        return [1, 'day', 1]
      case '5min':
        return [1, 'day', 5]
      case '15min':
        return [1, 'day', 15]
      case '30min':
        return [1, 'day', 30]
      case '1hour':
        return [5, 'day', 60]
      case '1day':
        return [1, 'month', 1]
      default:
        return [1, 'day', 1]  // Default to 1min (valid)
    }
  }

  const prepareCandlestickData = () => {
    if (!chartData || !chartData.candles) return null

    const candles = chartData.candles
    const labels = candles.map(c => {
      const date = new Date(c.time)
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    })

    // Prepare candlestick data format: [time, open, high, low, close]
    const candlestickData = candles.map(c => ({
      x: c.time,
      o: c.open,
      h: c.high,
      l: c.low,
      c: c.close
    }))

    // Get moving averages - Always calculate for all timeframes
    const mm8 = chartData.indicators?.sma_8?.map(i => ({ x: i.time, y: i.value })) || []
    const mm20 = chartData.indicators?.sma_20?.map(i => ({ x: i.time, y: i.value })) || []
    const mm200 = chartData.indicators?.sma_200?.map(i => ({ x: i.time, y: i.value })) || []

    // Store candlestick data for custom rendering
    const datasets = [
      {
        label: 'Price',
        data: candlestickData.map(c => ({ x: c.x, y: c.c })),
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        borderWidth: 0,
        pointRadius: 0,
        fill: false,
        yAxisID: 'y',
        // Store full OHLC data for custom rendering
        _candlestickData: candlestickData
      }
    ]

    // Add MM8 (red line - fast) - Always show on all timeframes
    if (mm8.length > 0) {
      datasets.push({
        label: 'MM8',
        data: mm8,
        borderColor: '#ef4444',  // Red
        backgroundColor: 'transparent',
        borderWidth: 2,  // Increased for better visibility
        pointRadius: 0,
        fill: false,
        yAxisID: 'y'
      })
    }

    // Add MM20 (yellow/gold line - medium) - Always show on all timeframes
    if (mm20.length > 0) {
      datasets.push({
        label: 'MM20',
        data: mm20,
        borderColor: '#f59e0b',  // Yellow/Gold
        backgroundColor: 'transparent',
        borderWidth: 2,  // Increased for better visibility
        pointRadius: 0,
        fill: false,
        yAxisID: 'y'
      })
    }

    // Add MM200 (blue line - slow) - Always show on all timeframes
    if (mm200.length > 0) {
      datasets.push({
        label: 'MM200',
        data: mm200,
        borderColor: '#3b82f6',  // Blue
        backgroundColor: 'transparent',
        borderWidth: 2.5,  // Slightly thicker for long-term trend
        pointRadius: 0,
        fill: false,
        yAxisID: 'y'
      })
    }

    return {
      labels,
      datasets
    }
  }

  const prepareVolumeData = () => {
    if (!chartData || !chartData.candles || !showIndicators.volume) return null

    const candles = chartData.candles
    const labels = candles.map(c => {
      const date = new Date(c.time)
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    })

    const volumes = candles.map(c => c.volume || 0)
    const colors = candles.map((c, i) => {
      if (i === 0) return '#9ca3af'
      return candles[i - 1].close <= c.close ? '#10b981' : '#ef4444'
    })

    return {
      labels,
      datasets: [{
        label: 'Volume',
        data: volumes,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 0,
        yAxisID: 'y1'
      }]
    }
  }

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top',
        labels: {
          color: '#9ca3af',
          usePointStyle: true,
          padding: 15,
          filter: (item) => item.text !== 'Candles' // Hide candlestick from legend
        }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: '#1a1f3a',
        titleColor: '#fff',
        bodyColor: '#e0e0e0',
        borderColor: '#667eea',
        borderWidth: 1,
        callbacks: {
          label: function(context) {
            if (context.dataset.type === 'candlestick') {
              const data = context.raw
              return [
                `Open: $${data.o.toFixed(2)}`,
                `High: $${data.h.toFixed(2)}`,
                `Low: $${data.l.toFixed(2)}`,
                `Close: $${data.c.toFixed(2)}`
              ]
            }
            return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`
          }
        }
      }
    },
    scales: {
      x: {
        type: 'category',  // Use category instead of time for now
        ticks: {
          color: '#9ca3af',
          maxTicksLimit: 12
        },
        grid: {
          color: '#2a2f4a'
        }
      },
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        ticks: {
          color: '#9ca3af',
          callback: function(value) {
            return '$' + value.toFixed(2)
          }
        },
        grid: {
          color: '#2a2f4a'
        }
      }
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    }
  }

  const volumeOptions = {
    ...chartOptions,
    scales: {
      x: chartOptions.scales.x,
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        ticks: {
          color: '#9ca3af'
        },
        grid: {
          display: false
        }
      }
    }
  }

  if (!selectedSymbol) {
    return (
      <div className="card">
        <h2>Real-Time Chart</h2>
        <p style={{ color: '#9ca3af', textAlign: 'center', padding: '20px' }}>
          Loading watchlist...
        </p>
      </div>
    )
  }

  const candlestickData = prepareCandlestickData()
  const volumeData = prepareVolumeData()

  return (
    <div className="card" style={compact ? { padding: '15px' } : {}}>
      {!compact && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <h2 style={{ margin: 0 }}>Real-Time Chart:</h2>
            {watchlist.length > 0 && (
              <select
                value={selectedSymbol}
                onChange={(e) => setSelectedSymbol(e.target.value)}
                style={{
                  padding: '8px 12px',
                  background: '#2a2f4a',
                  border: '1px solid #2a2f4a',
                  borderRadius: '5px',
                  color: '#e0e0e0',
                  fontSize: '14px',
                  fontWeight: 'bold'
                }}
              >
                {watchlist.map(sym => (
                  <option key={sym} value={sym}>{sym}</option>
                ))}
              </select>
            )}
            {watchlist.length === 0 && (
              <span style={{ color: '#667eea', fontWeight: 'bold' }}>{selectedSymbol}</span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
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
            <button
              onClick={loadChartData}
              disabled={loading}
              className="btn"
              style={{ padding: '8px 16px' }}
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>
      )}
      {compact && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0, fontSize: '16px' }}>{selectedSymbol}</h3>
          <span style={{ color: '#9ca3af', fontSize: '12px' }}>{timeframe}</span>
        </div>
      )}

      <div style={{ marginBottom: '15px', display: 'flex', gap: '15px', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <span style={{ color: '#ef4444', fontWeight: 'bold' }}>● MM8</span>
          <span style={{ color: '#f59e0b', fontWeight: 'bold' }}>● MM20</span>
          <span style={{ color: '#3b82f6', fontWeight: 'bold' }}>● MM200</span>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#9ca3af', fontSize: '14px' }}>
          <input
            type="checkbox"
            checked={showIndicators.volume}
            onChange={(e) => setShowIndicators({ ...showIndicators, volume: e.target.checked })}
            style={{ marginRight: '5px' }}
          />
          Volume
        </label>
      </div>

      {error && (
        <div style={{
          padding: '15px',
          background: '#2a1f1f',
          border: '1px solid #ef4444',
          borderRadius: '5px',
          color: '#fca5a5',
          marginBottom: '15px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
          Loading chart data...
        </div>
      )}

      {candlestickData && !loading && (
        <div>
          <div style={{ height: compact ? '300px' : '500px', marginBottom: compact ? '10px' : '20px', background: '#0f0f0f', borderRadius: '5px', padding: '10px' }}>
            <Line 
              data={candlestickData} 
              options={chartOptions}
              plugins={[{
                id: 'candlestick',
                afterDatasetsDraw: (chart) => {
                  const ctx = chart.ctx
                  const meta = chart.getDatasetMeta(0)
                  const dataset = chart.data.datasets[0]
                  const candlestickData = dataset._candlestickData
                  
                  if (!candlestickData || !meta.data) return
                  
                  const yScale = chart.scales.y
                  
                  candlestickData.forEach((candle, index) => {
                    if (index >= meta.data.length) return
                    
                    const point = meta.data[index]
                    if (!point) return
                    
                    const x = point.x
                    const yOpen = yScale.getPixelForValue(candle.o)
                    const yClose = yScale.getPixelForValue(candle.c)
                    const yHigh = yScale.getPixelForValue(candle.h)
                    const yLow = yScale.getPixelForValue(candle.l)
                    
                    const isUp = candle.c >= candle.o
                    // Use brighter, more visible colors for candles
                    const color = isUp ? '#22c55e' : '#f87171'  // Brighter green/red
                    const borderColor = isUp ? '#16a34a' : '#dc2626'  // Darker border
                    
                    // Draw wick (high-low line) - make it thicker and more visible
                    ctx.strokeStyle = color
                    ctx.lineWidth = 2  // Increased from 1
                    ctx.beginPath()
                    ctx.moveTo(x, yHigh)
                    ctx.lineTo(x, yLow)
                    ctx.stroke()
                    
                    // Draw body (open-close rectangle) - make it wider and more visible
                    const bodyTop = Math.min(yOpen, yClose)
                    const bodyBottom = Math.max(yOpen, yClose)
                    const bodyHeight = Math.max(bodyBottom - bodyTop, 2)  // Minimum 2px height
                    const bodyWidth = 10  // Increased from 6 to 10 for better visibility
                    
                    ctx.fillStyle = color
                    ctx.fillRect(x - bodyWidth/2, bodyTop, bodyWidth, bodyHeight)
                    // Add border for better definition
                    ctx.strokeStyle = borderColor
                    ctx.lineWidth = 1.5
                    ctx.strokeRect(x - bodyWidth/2, bodyTop, bodyWidth, bodyHeight)
                  })
                }
              }]}
            />
          </div>

          {showIndicators.volume && volumeData && (
            <div style={{ height: compact ? '100px' : '150px', marginBottom: compact ? '10px' : '20px' }}>
              <Bar data={volumeData} options={volumeOptions} />
            </div>
          )}
        </div>
      )}

      {chartData && !compact && (
        <div style={{ marginTop: '15px', padding: '10px', background: '#2a2f4a', borderRadius: '5px', fontSize: '12px', color: '#9ca3af' }}>
          Last update: {new Date(chartData.metadata.last_update).toLocaleString()} | 
          Candles: {chartData.metadata.total_candles} | 
          Period: {chartData.metadata.period_type} | 
          Frequency: {chartData.metadata.frequency}min | 
          Hours: 8:00 AM - 4:10 PM ET
        </div>
      )}
    </div>
  )
}

export default RealTimeChart

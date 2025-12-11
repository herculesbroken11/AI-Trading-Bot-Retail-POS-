import React, { useState, useEffect, useRef } from 'react'
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts'
import { getWatchlist } from '../services/api'
import './Card.css'

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

  // Chart refs
  const chartContainerRef = useRef(null)
  const chartInstanceRef = useRef(null)
  const candlestickSeriesRef = useRef(null)
  const mm8SeriesRef = useRef(null)
  const mm20SeriesRef = useRef(null)
  const mm200SeriesRef = useRef(null)
  const volumeSeriesRef = useRef(null)

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

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return

    // Wait for container to have a width
    const initChart = () => {
      if (!chartContainerRef.current) return
      
      const containerWidth = chartContainerRef.current.clientWidth
      if (containerWidth === 0) {
        // Container not ready yet, try again
        setTimeout(initChart, 100)
        return
      }

      // Remove existing chart if any
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove()
        chartInstanceRef.current = null
      }

      // Create chart instance
      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: { type: ColorType.Solid, color: '#0f0f0f' },
          textColor: '#9ca3af',
        },
        grid: {
          vertLines: { color: '#2a2f4a' },
          horzLines: { color: '#2a2f4a' },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
        },
        rightPriceScale: {
          borderColor: '#2a2f4a',
          scaleMargins: {
            top: 0.1,
            bottom: 0.1,
          },
        },
        timeScale: {
          borderColor: '#2a2f4a',
          timeVisible: true,
          secondsVisible: false,
        },
        width: containerWidth,
        height: compact ? 300 : 500,
        autoSize: true,
      })

      chartInstanceRef.current = chart

      // Create candlestick series with very clear, visible candles
      const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',      // Bright green for up candles
      downColor: '#f87171',   // Bright red for down candles
      borderVisible: true,
      wickUpColor: '#22c55e',
      wickDownColor: '#f87171',
      borderUpColor: '#16a34a',  // Darker green border
      borderDownColor: '#dc2626', // Darker red border
      priceScaleId: 'right',
      priceFormat: {
        type: 'price',
        precision: 2,
        minMove: 0.01,
      },
    })
    candlestickSeriesRef.current = candlestickSeries

      // Create MM8 line (red - fast)
      const mm8Series = chart.addLineSeries({
        color: '#ef4444',
        lineWidth: 2,
        title: 'MM8',
        priceScaleId: 'right',
        priceFormat: {
          type: 'price',
          precision: 2,
          minMove: 0.01,
        },
      })
      mm8SeriesRef.current = mm8Series

      // Create MM20 line (yellow/gold - medium)
      const mm20Series = chart.addLineSeries({
        color: '#f59e0b',
        lineWidth: 2,
        title: 'MM20',
        priceScaleId: 'right',
        priceFormat: {
          type: 'price',
          precision: 2,
          minMove: 0.01,
        },
      })
      mm20SeriesRef.current = mm20Series

      // Create MM200 line (blue - slow)
      const mm200Series = chart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2.5,
        title: 'MM200',
        priceScaleId: 'right',
        priceFormat: {
          type: 'price',
          precision: 2,
          minMove: 0.01,
        },
      })
      mm200SeriesRef.current = mm200Series

      // Create volume histogram (overlay on main chart)
      const volumeSeries = chart.addHistogramSeries({
        color: '#667eea',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
      })
      volumeSeriesRef.current = volumeSeries

      // Create volume price scale (right side, separate from price)
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.85,
          bottom: 0,
        },
      })

      // Note: Data will be set via useEffect when chartData changes
    }

    // Initialize chart
    initChart()

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        const containerWidth = chartContainerRef.current.clientWidth
        if (containerWidth > 0) {
          chartInstanceRef.current.applyOptions({
            width: containerWidth,
          })
        }
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove()
        chartInstanceRef.current = null
      }
    }
  }, [compact])

  // Function to update chart data
  const updateChartData = (data) => {
    if (!data || !chartInstanceRef.current) return

    const candles = data.candles || []
    const indicators = data.indicators || {}

    // Prepare candlestick data
    const candlestickData = candles.map(c => ({
      time: Math.floor(new Date(c.time).getTime() / 1000), // Unix timestamp in seconds
      open: parseFloat(c.open),
      high: parseFloat(c.high),
      low: parseFloat(c.low),
      close: parseFloat(c.close),
    }))

    // Update candlestick series
    if (candlestickSeriesRef.current) {
      candlestickSeriesRef.current.setData(candlestickData)
    }

    // Prepare MM8 data - Always show on all timeframes
    if (showIndicators.mm8 && indicators.sma_8) {
      const mm8Data = indicators.sma_8
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => ({
          time: Math.floor(new Date(i.time).getTime() / 1000),
          value: parseFloat(i.value),
        }))
      if (mm8SeriesRef.current && mm8Data.length > 0) {
        mm8SeriesRef.current.setData(mm8Data)
        mm8SeriesRef.current.applyOptions({ visible: true })
      }
    } else if (mm8SeriesRef.current) {
      mm8SeriesRef.current.applyOptions({ visible: false })
    }

    // Prepare MM20 data - Always show on all timeframes
    if (showIndicators.mm20 && indicators.sma_20) {
      const mm20Data = indicators.sma_20
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => ({
          time: Math.floor(new Date(i.time).getTime() / 1000),
          value: parseFloat(i.value),
        }))
      if (mm20SeriesRef.current && mm20Data.length > 0) {
        mm20SeriesRef.current.setData(mm20Data)
        mm20SeriesRef.current.applyOptions({ visible: true })
      }
    } else if (mm20SeriesRef.current) {
      mm20SeriesRef.current.applyOptions({ visible: false })
    }

    // Prepare MM200 data - Always show on all timeframes
    if (showIndicators.mm200 && indicators.sma_200) {
      const mm200Data = indicators.sma_200
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => ({
          time: Math.floor(new Date(i.time).getTime() / 1000),
          value: parseFloat(i.value),
        }))
      if (mm200SeriesRef.current && mm200Data.length > 0) {
        mm200SeriesRef.current.setData(mm200Data)
        mm200SeriesRef.current.applyOptions({ visible: true })
      }
    } else if (mm200SeriesRef.current) {
      mm200SeriesRef.current.applyOptions({ visible: false })
    }

    // Prepare volume data
    if (showIndicators.volume) {
      const volumeData = candles.map((c, index) => {
        const prevClose = index > 0 ? parseFloat(candles[index - 1].close) : parseFloat(c.close)
        const currentClose = parseFloat(c.close)
        const isUp = currentClose >= prevClose

        return {
          time: Math.floor(new Date(c.time).getTime() / 1000),
          value: parseFloat(c.volume || 0),
          color: isUp ? '#10b981' : '#ef4444',
        }
      })

      if (volumeSeriesRef.current) {
        volumeSeriesRef.current.setData(volumeData)
        volumeSeriesRef.current.applyOptions({ visible: true })
      }
    } else if (volumeSeriesRef.current) {
      volumeSeriesRef.current.applyOptions({ visible: false })
    }

    // Fit content
    if (chartInstanceRef.current) {
      chartInstanceRef.current.timeScale().fitContent()
    }
  }

  // Update chart data when chartData changes
  useEffect(() => {
    if (!chartData) return
    
    // Wait for chart to be ready, then update
    const tryUpdate = () => {
      if (chartInstanceRef.current && candlestickSeriesRef.current) {
        updateChartData(chartData)
      } else {
        // Chart not ready yet, try again in 100ms
        setTimeout(tryUpdate, 100)
      }
    }
    
    tryUpdate()
  }, [chartData, showIndicators])

  // Update chart height when compact prop changes
  useEffect(() => {
    if (chartInstanceRef.current && chartContainerRef.current) {
      chartInstanceRef.current.applyOptions({
        height: compact ? 300 : 500,
      })
    }
  }, [compact])

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
          <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#ef4444', fontWeight: 'bold', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showIndicators.mm8}
              onChange={(e) => setShowIndicators({ ...showIndicators, mm8: e.target.checked })}
              style={{ marginRight: '5px' }}
            />
            MM8
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#f59e0b', fontWeight: 'bold', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showIndicators.mm20}
              onChange={(e) => setShowIndicators({ ...showIndicators, mm20: e.target.checked })}
              style={{ marginRight: '5px' }}
            />
            MM20
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#3b82f6', fontWeight: 'bold', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showIndicators.mm200}
              onChange={(e) => setShowIndicators({ ...showIndicators, mm200: e.target.checked })}
              style={{ marginRight: '5px' }}
            />
            MM200
          </label>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#9ca3af', fontSize: '14px', cursor: 'pointer' }}>
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

      <div style={{ position: 'relative' }}>
        <div 
          ref={chartContainerRef} 
          style={{ 
            width: '100%', 
            height: compact ? '300px' : '500px',
            background: '#0f0f0f',
            borderRadius: '5px'
          }} 
        />
      </div>

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

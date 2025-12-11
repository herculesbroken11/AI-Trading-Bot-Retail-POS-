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

  // Function to update chart data
  const updateChartData = (data) => {
    if (!data || !chartInstanceRef.current) {
      console.log('Cannot update chart data:', { hasData: !!data, hasChart: !!chartInstanceRef.current })
      return
    }

    const candles = data.candles || []
    const indicators = data.indicators || {}

    console.log('Updating chart with data:', { 
      candles: candles.length, 
      hasIndicators: !!indicators,
      sma_8_count: indicators.sma_8?.length || 0,
      sma_20_count: indicators.sma_20?.length || 0,
      sma_200_count: indicators.sma_200?.length || 0,
      timeframe: timeframe
    })

    // Prepare candlestick data
    const candlestickData = candles.map(c => {
      // Handle both timestamp (number in ms) and ISO string formats
      let timestamp
      if (typeof c.time === 'number') {
        timestamp = Math.floor(c.time / 1000) // Convert ms to seconds
      } else if (typeof c.time === 'string') {
        timestamp = Math.floor(new Date(c.time).getTime() / 1000)
      } else {
        console.warn('Invalid candle time format:', c.time)
        timestamp = 0
      }
      return {
        time: timestamp,
        open: parseFloat(c.open),
        high: parseFloat(c.high),
        low: parseFloat(c.low),
        close: parseFloat(c.close),
      }
    })

    // Update candlestick series
    if (candlestickSeriesRef.current) {
      candlestickSeriesRef.current.setData(candlestickData)
      console.log('Candlestick data set:', candlestickData.length, 'candles')
    } else {
      console.error('Candlestick series not available')
    }

    // Prepare MM8 data - Always show on all timeframes
    if (showIndicators.mm8 && indicators.sma_8) {
      const mm8Data = indicators.sma_8
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => {
          // Handle both timestamp (number) and ISO string formats
          let timestamp
          if (typeof i.time === 'number') {
            timestamp = Math.floor(i.time / 1000) // Convert ms to seconds
          } else if (typeof i.time === 'string') {
            timestamp = Math.floor(new Date(i.time).getTime() / 1000)
          } else {
            console.warn('Invalid MM8 time format:', i.time)
            return null
          }
          return {
            time: timestamp,
            value: parseFloat(i.value),
          }
        })
        .filter(i => i !== null)
      
      console.log(`MM8 data: ${mm8Data.length} points (from ${indicators.sma_8.length} total)`)
      if (mm8SeriesRef.current) {
        if (mm8Data.length > 0) {
          mm8SeriesRef.current.setData(mm8Data)
          mm8SeriesRef.current.applyOptions({ visible: true })
          console.log('MM8 series updated and made visible')
        } else {
          console.warn('MM8 data is empty after filtering')
          mm8SeriesRef.current.applyOptions({ visible: false })
        }
      } else {
        console.error('MM8 series ref not available')
      }
    } else if (mm8SeriesRef.current) {
      mm8SeriesRef.current.applyOptions({ visible: false })
    }

    // Prepare MM20 data - Always show on all timeframes
    if (showIndicators.mm20 && indicators.sma_20) {
      const mm20Data = indicators.sma_20
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => {
          // Handle both timestamp (number) and ISO string formats
          let timestamp
          if (typeof i.time === 'number') {
            timestamp = Math.floor(i.time / 1000) // Convert ms to seconds
          } else if (typeof i.time === 'string') {
            timestamp = Math.floor(new Date(i.time).getTime() / 1000)
          } else {
            console.warn('Invalid MM20 time format:', i.time)
            return null
          }
          return {
            time: timestamp,
            value: parseFloat(i.value),
          }
        })
        .filter(i => i !== null)
      
      console.log(`MM20 data: ${mm20Data.length} points (from ${indicators.sma_20.length} total)`)
      if (mm20SeriesRef.current) {
        if (mm20Data.length > 0) {
          mm20SeriesRef.current.setData(mm20Data)
          mm20SeriesRef.current.applyOptions({ visible: true })
          console.log('MM20 series updated and made visible')
        } else {
          console.warn('MM20 data is empty after filtering')
          mm20SeriesRef.current.applyOptions({ visible: false })
        }
      } else {
        console.error('MM20 series ref not available')
      }
    } else if (mm20SeriesRef.current) {
      mm20SeriesRef.current.applyOptions({ visible: false })
    }

    // Prepare MM200 data - Always show on all timeframes
    if (showIndicators.mm200 && indicators.sma_200) {
      const mm200Data = indicators.sma_200
        .filter(i => i.value !== null && i.value !== undefined)
        .map(i => {
          // Handle both timestamp (number) and ISO string formats
          let timestamp
          if (typeof i.time === 'number') {
            timestamp = Math.floor(i.time / 1000) // Convert ms to seconds
          } else if (typeof i.time === 'string') {
            timestamp = Math.floor(new Date(i.time).getTime() / 1000)
          } else {
            console.warn('Invalid MM200 time format:', i.time)
            return null
          }
          return {
            time: timestamp,
            value: parseFloat(i.value),
          }
        })
        .filter(i => i !== null)
      
      console.log(`MM200 data: ${mm200Data.length} points available (total indicators: ${indicators.sma_200?.length || 0})`)
      if (mm200SeriesRef.current) {
        if (mm200Data.length > 0) {
          mm200SeriesRef.current.setData(mm200Data)
          mm200SeriesRef.current.applyOptions({ visible: true })
          console.log('MM200 series updated and made visible')
        } else {
          console.warn('MM200 data is empty - may need more historical data')
          mm200SeriesRef.current.applyOptions({ visible: false })
        }
      } else {
        console.error('MM200 series ref not available')
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
      console.log('Chart content fitted')
    }
  }

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) {
      console.log('Chart container ref not available')
      return
    }

    // Wait for container to have a width
    const initChart = () => {
      if (!chartContainerRef.current) {
        console.log('Chart container lost during init')
        return
      }
      
      const containerWidth = chartContainerRef.current.clientWidth
      const containerHeight = chartContainerRef.current.clientHeight
      
      if (containerWidth === 0 || containerHeight === 0) {
        // Container not ready yet, try again
        console.log('Container not ready, retrying...', { containerWidth, containerHeight })
        setTimeout(initChart, 100)
        return
      }

      console.log('Initializing chart with dimensions:', { containerWidth, containerHeight, compact })

      // Remove existing chart if any
      if (chartInstanceRef.current) {
        console.log('Removing existing chart')
        chartInstanceRef.current.remove()
        chartInstanceRef.current = null
        candlestickSeriesRef.current = null
        mm8SeriesRef.current = null
        mm20SeriesRef.current = null
        mm200SeriesRef.current = null
        volumeSeriesRef.current = null
      }

      try {
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
          height: containerHeight,
        })

        chartInstanceRef.current = chart
        console.log('Chart instance created')

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
        console.log('Candlestick series created')

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

        console.log('All chart series created successfully')

        // If data already exists, set it immediately
        if (chartData) {
          console.log('Setting initial chart data')
          setTimeout(() => updateChartData(chartData), 100)
        }
      } catch (error) {
        console.error('Error creating chart:', error)
        setError(`Chart initialization error: ${error.message}`)
      }
    }

    // Initialize chart with a small delay to ensure DOM is ready
    const timeoutId = setTimeout(initChart, 50)

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartInstanceRef.current) {
        const containerWidth = chartContainerRef.current.clientWidth
        const containerHeight = chartContainerRef.current.clientHeight
        if (containerWidth > 0 && containerHeight > 0) {
          chartInstanceRef.current.applyOptions({
            width: containerWidth,
            height: containerHeight,
          })
        }
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      clearTimeout(timeoutId)
      window.removeEventListener('resize', handleResize)
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove()
        chartInstanceRef.current = null
        candlestickSeriesRef.current = null
        mm8SeriesRef.current = null
        mm20SeriesRef.current = null
        mm200SeriesRef.current = null
        volumeSeriesRef.current = null
      }
    }
  }, [compact, chartData])

  // Update chart data when chartData changes
  useEffect(() => {
    if (!chartData) {
      console.log('No chart data to update')
      return
    }
    
    console.log('Chart data changed, updating chart...', {
      hasChart: !!chartInstanceRef.current,
      hasCandlestick: !!candlestickSeriesRef.current,
      candles: chartData.candles?.length || 0
    })
    
    // Wait for chart to be ready, then update
    let retryCount = 0
    const maxRetries = 50 // 5 seconds max wait
    
    const tryUpdate = () => {
      if (chartInstanceRef.current && candlestickSeriesRef.current) {
        console.log('Chart ready, updating data')
        try {
          updateChartData(chartData)
          console.log('Chart data updated successfully')
        } catch (error) {
          console.error('Error updating chart data:', error)
          setError(`Chart update error: ${error.message}`)
        }
      } else if (retryCount < maxRetries) {
        retryCount++
        setTimeout(tryUpdate, 100)
      } else {
        console.error('Chart not ready after max retries')
        setError('Chart failed to initialize. Please refresh the page.')
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
    // Request enough days to ensure we have 200+ candles for SMA200 calculation
    // After filtering to 8 AM - 4:10 PM ET, we get ~480 minutes per day
    switch (tf) {
      case '1min':
        return [10, 'day', 1]  // Request 10 days for enough data (480 candles/day)
      case '2min':
        // 2min not supported, use 1min instead
        return [10, 'day', 1]  // Request 10 days
      case '5min':
        return [10, 'day', 5]  // Request 10 days (96 candles/day)
      case '15min':
        return [10, 'day', 15]  // Request 10 days (32 candles/day)
      case '30min':
        return [10, 'day', 30]  // Request 10 days (16 candles/day)
      case '1hour':
        return [10, 'day', 60]
      case '1day':
        return [1, 'month', 1]
      default:
        return [10, 'day', 1]  // Default to 10 days for enough data
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

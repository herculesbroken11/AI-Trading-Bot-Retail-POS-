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
  const [viewMode, setViewMode] = useState('today') // 'today', 'yesterday', 'lastWeek', 'lastMonth', 'custom'
  const [customDate, setCustomDate] = useState('')
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
  
  // Real-time streaming refs
  const realtimePollIntervalRef = useRef(null)
  const lastCandleTimeRef = useRef(null)

  useEffect(() => {
    // Load watchlist from automation status
    loadWatchlist()
  }, [])

  useEffect(() => {
    // Update selected symbol if prop changes, but only if it's in the watchlist
    if (propSymbol && propSymbol !== selectedSymbol) {
      // Only set if it's in the watchlist
      if (watchlist.length === 0 || watchlist.includes(propSymbol.toUpperCase())) {
        setSelectedSymbol(propSymbol)
      } else {
        console.warn(`Symbol ${propSymbol} is not in TRADING_WATCHLIST, ignoring`)
      }
    }
  }, [propSymbol, watchlist])

  useEffect(() => {
    if (propTimeframe && propTimeframe !== timeframe) {
      setTimeframe(propTimeframe)
    }
  }, [propTimeframe])

  useEffect(() => {
    if (selectedSymbol) {
      loadChartData()
      // Only subscribe to real-time data if viewing today (not historical)
      if (viewMode === 'today') {
        subscribeToRealtimeChart(selectedSymbol)
      } else {
        // Unsubscribe if switching to historical view
        unsubscribeFromRealtimeChart(selectedSymbol)
      }
    }
    
    // Cleanup on unmount or symbol change
    return () => {
      if (realtimePollIntervalRef.current) {
        clearInterval(realtimePollIntervalRef.current)
        realtimePollIntervalRef.current = null
      }
      if (selectedSymbol) {
        unsubscribeFromRealtimeChart(selectedSymbol)
      }
    }
  }, [selectedSymbol, timeframe, lastUpdate, viewMode, customDate])

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
      // Timestamps from backend are Unix timestamps in milliseconds (UTC-based)
      // TradingView chart will display them in ET timezone based on timeZone setting
      let timestamp
      if (typeof c.time === 'number') {
        timestamp = Math.floor(c.time / 1000) // Convert ms to seconds (TradingView expects seconds)
      } else if (typeof c.time === 'string') {
        timestamp = Math.floor(new Date(c.time).getTime() / 1000)
      } else {
        console.warn('Invalid candle time format:', c.time)
        timestamp = 0
      }
      
      // Debug: Log first and last timestamps to verify timezone conversion
      if (candles.indexOf(c) === 0 || candles.indexOf(c) === candles.length - 1) {
        const date = new Date(timestamp * 1000)
        const utcTime = date.toISOString()
        const etTime = date.toLocaleString('en-US', { 
          timeZone: 'America/New_York',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true
        })
        const etTime24 = date.toLocaleString('en-US', {
          timeZone: 'America/New_York',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        })
        console.log(`Candle timestamp: ${timestamp} (Unix seconds)`)
        console.log(`  UTC: ${utcTime}`)
        console.log(`  ET:  ${etTime} (${etTime24})`)
        console.log(`  Chart should display: ${etTime} (ET timezone)`)
        console.log(`  Chart timezone setting: America/New_York`)
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

    // Re-apply timezone setting after data update to ensure it's still active
    if (chartInstanceRef.current) {
      chartInstanceRef.current.timeScale().applyOptions({
        timeZone: 'America/New_York',
        timeVisible: true,
        secondsVisible: false
      })
      chartInstanceRef.current.timeScale().fitContent()
      console.log('Chart content fitted with ET timezone')
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
            rightOffset: 0,
            barSpacing: 3,
            fixLeftEdge: false,
            fixRightEdge: false,
            lockVisibleTimeRangeOnResize: false,
            rightBarStaysOnScroll: false,
            shiftVisibleRangeOnNewBar: false,
            // Display times in ET timezone
            timeZone: 'America/New_York',
            visible: true,
          },
          width: containerWidth,
          height: containerHeight,
        })

        chartInstanceRef.current = chart
        console.log('Chart instance created')
        
        // Explicitly apply timezone setting to ensure ET timezone is used
        // This ensures the chart displays times in America/New_York timezone
        // Set timezone explicitly - this must be done after chart creation
        chart.timeScale().applyOptions({
          timeZone: 'America/New_York',
          timeVisible: true,
          secondsVisible: false
        })
        console.log('Chart timezone set to America/New_York (ET)')
        
        // Listen for visible range changes to detect zoom out
        // When user zooms out significantly, we can fetch more historical data
        chart.timeScale().subscribeVisibleTimeRangeChange((timeRange) => {
          if (timeRange && timeRange.from && timeRange.to) {
            const fromDate = new Date(timeRange.from * 1000)
            const toDate = new Date(timeRange.to * 1000)
            const daysDiff = (toDate - fromDate) / (1000 * 60 * 60 * 24)
            
            // If user zooms out to see more than 15 days, fetch more historical data
            if (daysDiff > 15 && viewMode === 'today') {
              console.log(`User zoomed out to ${daysDiff.toFixed(1)} days, fetching more historical data...`)
              // Note: For now, we'll just log this. In the future, we can implement
              // a mechanism to fetch more data when zooming out significantly
            }
          }
        })

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
        
        // Verify and enforce timezone setting
        // TradingView Lightweight Charts should use the timezone from timeScale config
        // But we'll verify it's set correctly and reapply if needed
        const currentTimezone = chart.timeScale().options().timeZone
        console.log(`Chart timezone setting: ${currentTimezone || 'not set (defaults to browser timezone)'}`)
        if (currentTimezone !== 'America/New_York') {
          console.warn('Chart timezone not set to America/New_York, applying now...')
          chart.timeScale().applyOptions({ 
            timeZone: 'America/New_York',
            timeVisible: true,
            secondsVisible: false
          })
          console.log('Chart timezone explicitly set to America/New_York (ET)')
        }

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
        // Set first symbol from watchlist if no symbol provided or if current symbol is not in watchlist
        if (!propSymbol && watchlistData.watchlist.length > 0) {
          setSelectedSymbol(watchlistData.watchlist[0])
        } else if (propSymbol && !watchlistData.watchlist.includes(propSymbol.toUpperCase())) {
          // If prop symbol is not in watchlist, use first watchlist symbol instead
          console.warn(`Prop symbol ${propSymbol} not in TRADING_WATCHLIST, using ${watchlistData.watchlist[0]}`)
          setSelectedSymbol(watchlistData.watchlist[0])
        } else if (selectedSymbol && !watchlistData.watchlist.includes(selectedSymbol.toUpperCase())) {
          // If current selected symbol is not in watchlist, use first watchlist symbol
          console.warn(`Current symbol ${selectedSymbol} not in TRADING_WATCHLIST, using ${watchlistData.watchlist[0]}`)
          setSelectedSymbol(watchlistData.watchlist[0])
        }
      } else {
        console.error('TRADING_WATCHLIST is empty or not configured. Please set TRADING_WATCHLIST in .env file.')
        setError('No watchlist configured. Please set TRADING_WATCHLIST in .env file.')
        setWatchlist([])
        // Clear selected symbol if watchlist is empty
        if (selectedSymbol) {
          setSelectedSymbol('')
        }
      }
    } catch (error) {
      console.error('Failed to load watchlist from /charts/watchlist:', error)
      setError(`Failed to load watchlist: ${error.message}. Please ensure TRADING_WATCHLIST is set in .env file.`)
      setWatchlist([])
    }
  }

  const loadChartData = async () => {
    if (!selectedSymbol) return
    
    // Validate that symbol is in watchlist
    if (watchlist.length > 0 && !watchlist.includes(selectedSymbol.toUpperCase())) {
      console.warn(`Symbol ${selectedSymbol} is not in TRADING_WATCHLIST, skipping chart load`)
      setError(`Symbol ${selectedSymbol} is not in trading watchlist. Only symbols from TRADING_WATCHLIST are allowed.`)
      return
    }
    
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
    // After filtering to 8 AM - 4:30 PM ET, we get ~510 minutes per day
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

  // Real-time chart subscription functions
  const subscribeToRealtimeChart = async (symbol) => {
    if (!symbol) return
    
    try {
      // Check if Streamer is already connected
      const statusResponse = await fetch(`${window.location.origin}/streaming/status`)
      let isConnected = false
      if (statusResponse.ok) {
        const status = await statusResponse.json()
        isConnected = status.connected && status.authenticated
      }
      
      // Only connect if not already connected
      if (!isConnected) {
        const connectResponse = await fetch(`${window.location.origin}/streaming/connect`, {
          method: 'POST'
        })
        
        if (!connectResponse.ok) {
          console.debug(`Streamer connection failed for ${symbol}, real-time updates disabled`)
          return
        }
        
        // Wait for connection and authentication to complete
        // Check status with retries
        let retries = 10
        while (retries > 0) {
          await new Promise(resolve => setTimeout(resolve, 500))
          const checkStatus = await fetch(`${window.location.origin}/streaming/status`)
          if (checkStatus.ok) {
            const status = await checkStatus.json()
            if (status.connected && status.authenticated) {
              isConnected = true
              break
            }
          }
          retries--
        }
        
        if (!isConnected) {
          console.debug(`Streamer did not connect in time for ${symbol}, real-time updates disabled`)
          return
        }
      }
      
      // Subscribe to CHART_EQUITY for this symbol
      const subscribeResponse = await fetch(`${window.location.origin}/streaming/subscribe/CHART_EQUITY/${symbol}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      
      if (subscribeResponse.ok) {
        console.log(`Subscribed to real-time chart data for ${symbol}`)
        
        // Start polling for latest candle data
        startRealtimePolling(symbol)
      } else {
        const errorData = await subscribeResponse.json().catch(() => ({}))
        console.debug(`Failed to subscribe to real-time chart data for ${symbol}: ${errorData.error || subscribeResponse.statusText}`)
      }
    } catch (error) {
      console.debug(`Error subscribing to real-time chart for ${symbol}: ${error.message}`)
    }
  }

  const unsubscribeFromRealtimeChart = async (symbol) => {
    if (!symbol) return
    
    try {
      await fetch(`${window.location.origin}/streaming/unsubscribe/CHART_EQUITY/${symbol}`, {
        method: 'POST'
      })
      
      if (realtimePollIntervalRef.current) {
        clearInterval(realtimePollIntervalRef.current)
        realtimePollIntervalRef.current = null
      }
      
      console.log(`Unsubscribed from real-time chart data for ${symbol}`)
    } catch (error) {
      console.error('Error unsubscribing from real-time chart:', error)
    }
  }

  const startRealtimePolling = (symbol) => {
    // Clear any existing interval
    if (realtimePollIntervalRef.current) {
      clearInterval(realtimePollIntervalRef.current)
    }
    
    // Check Streamer status first
    const checkAndPoll = async () => {
      try {
        // Check if Streamer is connected
        const statusResponse = await fetch(`${window.location.origin}/streaming/status`)
        if (statusResponse.ok) {
          const status = await statusResponse.json()
          if (!status.connected || !status.authenticated) {
            // Streamer not connected, don't poll
            console.debug(`Streamer not connected for ${symbol}, skipping real-time polling`)
            return
          }
        }
        
        // Poll for latest candle
        const response = await fetch(`${window.location.origin}/streaming/chart/latest/${symbol}`)
        if (response.ok) {
          const data = await response.json()
          if (data.has_data && data.candle) {
            const candle = data.candle
            
            // Check if this is a new candle (different timestamp)
            if (lastCandleTimeRef.current !== candle.timestamp) {
              lastCandleTimeRef.current = candle.timestamp
              
              // Update chart with new candle
              updateRealtimeCandle(candle)
            }
          }
        } else if (response.status === 404) {
          // 404 is expected when Streamer isn't connected or no data yet - silently skip
          // Don't log as error, it's normal when Streamer isn't active
        }
      } catch (error) {
        // Only log non-404 errors
        if (!error.message || !error.message.includes('404')) {
          console.debug(`Real-time polling for ${symbol}: ${error.message}`)
        }
      }
    }
    
    // Poll every 2 seconds (reduced frequency to avoid too many requests)
    // First check immediately
    checkAndPoll()
    
    // Then set up interval
    realtimePollIntervalRef.current = setInterval(checkAndPoll, 2000) // Poll every 2 seconds
  }

  const updateRealtimeCandle = (candle) => {
    if (!candlestickSeriesRef.current || !candle.time) return
    
    try {
      // Convert timestamp to seconds (TradingView expects seconds)
      const timeInSeconds = Math.floor(candle.time / 1000)
      
      // Update or append the candle
      const candleData = {
        time: timeInSeconds,
        open: parseFloat(candle.open),
        high: parseFloat(candle.high),
        low: parseFloat(candle.low),
        close: parseFloat(candle.close),
      }
      
      // Use update() for real-time updates (updates the last candle or appends new one)
      candlestickSeriesRef.current.update(candleData)
      
      // Update volume if available
      if (volumeSeriesRef.current && candle.volume !== undefined) {
        const volumeData = {
          time: timeInSeconds,
          value: parseFloat(candle.volume),
          color: candle.close >= candle.open ? '#10b981' : '#ef4444',
        }
        volumeSeriesRef.current.update(volumeData)
      }
      
      console.log('Real-time candle updated:', candleData)
    } catch (error) {
      console.error('Error updating real-time candle:', error)
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
                value={watchlist.includes(selectedSymbol.toUpperCase()) ? selectedSymbol.toUpperCase() : watchlist[0]}
                onChange={(e) => {
                  const newSymbol = e.target.value.toUpperCase()
                  // Ensure selected symbol is in watchlist
                  if (watchlist.includes(newSymbol)) {
                    setSelectedSymbol(newSymbol)
                  } else {
                    // Fallback to first symbol in watchlist if invalid
                    console.warn(`Symbol ${newSymbol} not in watchlist, using ${watchlist[0]}`)
                    setSelectedSymbol(watchlist[0])
                  }
                }}
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
              <span style={{ color: '#ef4444', fontWeight: 'bold' }}>
                No watchlist configured. Please set TRADING_WATCHLIST in .env file.
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
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
              <option value="1min">1 Min</option>
              <option value="2min">2 Min</option>
              <option value="5min">5 Min</option>
              <option value="15min">15 Min</option>
              <option value="30min">30 Min</option>
              <option value="1hour">1 Hour</option>
              <option value="1day">1 Day</option>
            </select>
            <select
              value={viewMode}
              onChange={(e) => {
                setViewMode(e.target.value)
                if (e.target.value !== 'custom') {
                  setCustomDate('')
                }
              }}
              style={{
                padding: '8px 12px',
                background: '#2a2f4a',
                border: '1px solid #2a2f4a',
                borderRadius: '5px',
                color: '#e0e0e0',
                fontSize: '14px'
              }}
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="lastWeek">Last 5 Days</option>
              <option value="lastMonth">Last 20 Days</option>
              <option value="custom">Custom Date</option>
            </select>
            {viewMode === 'custom' && (
              <input
                type="date"
                value={customDate}
                onChange={(e) => setCustomDate(e.target.value)}
                style={{
                  padding: '8px 12px',
                  background: '#2a2f4a',
                  border: '1px solid #2a2f4a',
                  borderRadius: '5px',
                  color: '#e0e0e0',
                  fontSize: '14px'
                }}
              />
            )}
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
          Hours: 8:00 AM - 4:30 PM ET
        </div>
      )}
    </div>
  )
}

export default RealTimeChart

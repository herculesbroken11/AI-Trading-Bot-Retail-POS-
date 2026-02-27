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
  // Date filter removed - chart shows all data without date filter
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
  const lastChartCandleTimeRef = useRef(null) // Track last candle time ON CHART (seconds) - prevents "Cannot update oldest data"
  
  // Track loaded data range for dynamic loading
  const loadedDataRangeRef = useRef({ earliest: null, latest: null, periodValue: 0 })
  const isLoadingOlderDataRef = useRef(false)

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

  // Effect 1: Load chart data when symbol, timeframe, viewMode, or refresh (lastUpdate) changes
  // NOTE: lastUpdate triggers refresh every 30s - we do NOT unsubscribe from real-time here
  useEffect(() => {
    if (selectedSymbol) {
      loadChartData()
    }
  }, [selectedSymbol, timeframe, lastUpdate])

  // Effect 2: Subscribe to real-time data (date filter removed - always show real-time)
  useEffect(() => {
    if (selectedSymbol) {
      subscribeToRealtimeChart(selectedSymbol)
    }

    return () => {
      if (realtimePollIntervalRef.current) {
        clearInterval(realtimePollIntervalRef.current)
        realtimePollIntervalRef.current = null
      }
      if (selectedSymbol) {
        unsubscribeFromRealtimeChart(selectedSymbol)
      }
    }
  }, [selectedSymbol])

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
    
    // Log first and last candle timestamps to verify date range
    if (candles.length > 0) {
      const firstCandle = candles[0]
      const lastCandle = candles[candles.length - 1]
      const firstTime = typeof firstCandle.time === 'number' ? new Date(firstCandle.time) : new Date(firstCandle.time)
      const lastTime = typeof lastCandle.time === 'number' ? new Date(lastCandle.time) : new Date(lastCandle.time)
      console.log(`📊 Chart data range: ${firstTime.toLocaleDateString()} ${firstTime.toLocaleTimeString()} to ${lastTime.toLocaleDateString()} ${lastTime.toLocaleTimeString()}`)
      console.log(`📊 Total candles: ${candles.length} (should show ${Math.ceil(candles.length / (510 / (timeframe === '1min' ? 1 : timeframe === '5min' ? 5 : timeframe === '15min' ? 15 : 1)))} days when zoomed out)`)
    }

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
        const utcHour = date.getUTCHours()
        const utcMin = date.getUTCMinutes()
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
        console.log(`  UTC: ${utcTime} (${utcHour.toString().padStart(2, '0')}:${utcMin.toString().padStart(2, '0')})`)
        console.log(`  ET:  ${etTime} (${etTime24})`)
        console.log(`  Chart should display: ${etTime} (ET timezone)`)
        console.log(`  Chart timezone setting: America/New_York`)
        console.warn(`⚠️ If chart shows ${utcHour}:${utcMin.toString().padStart(2, '0')} instead of ${etTime24}, timezone is NOT working!`)
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
      console.log(`✅ Candlestick data set: ${candlestickData.length} candles`)
      
      // Track last candle time on chart - required for real-time updates (prevents "Cannot update oldest data")
      if (candlestickData.length > 0) {
        lastChartCandleTimeRef.current = candlestickData[candlestickData.length - 1].time
      }
      
      // Log date range of loaded data
      if (candlestickData.length > 0) {
        const firstCandle = candlestickData[0]
        const lastCandle = candlestickData[candlestickData.length - 1]
        const firstDate = new Date(firstCandle.time * 1000)
        const lastDate = new Date(lastCandle.time * 1000)
        const daysDiff = (lastDate - firstDate) / (1000 * 60 * 60 * 24)
        console.log(`📊 Chart loaded ${daysDiff.toFixed(1)} days of data: ${firstDate.toLocaleDateString()} to ${lastDate.toLocaleDateString()}`)
        console.log(`📊 All ${candlestickData.length} candles are loaded - zoom out to see all historical data`)
      }
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
      try {
        // Force timezone update - try both formats
        const timeScale = chartInstanceRef.current.timeScale()
        timeScale.applyOptions({
          timeZone: 'America/New_York',
          timeVisible: true,
          secondsVisible: false
        })
        
        // Verify timezone was applied
        const currentOptions = timeScale.options()
        console.log('Chart timezone after update:', currentOptions.timeZone)
        
        // Fit content to show all data - this allows zooming out to see all historical data
        timeScale.fitContent()
        console.log('Chart content fitted - all data should be visible when zoomed out')
        
        // Log visible range after fitting to verify all data is shown
        const visibleRange = timeScale.getVisibleRange()
        if (visibleRange) {
          const fromDate = new Date(visibleRange.from * 1000)
          const toDate = new Date(visibleRange.to * 1000)
          const daysDiff = (toDate - fromDate) / (1000 * 60 * 60 * 24)
          console.log(`Chart visible range after fitContent: ${fromDate.toLocaleDateString()} to ${toDate.toLocaleDateString()} (${daysDiff.toFixed(1)} days)`)
        }
      } catch (e) {
        console.error('Error applying timezone after data update:', e)
        // Try fallback
        try {
          chartInstanceRef.current.timeScale().applyOptions({
            timeZone: 'US/Eastern',
            timeVisible: true,
            secondsVisible: false
          })
          chartInstanceRef.current.timeScale().fitContent()
        } catch (e2) {
          console.error('Failed to apply fallback timezone:', e2)
        }
      }
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
            timeZone: 'America/New_York', // Set timezone in initial options - this should convert UTC timestamps to ET
            visible: true,
          },
          width: containerWidth,
          height: containerHeight,
        })

        chartInstanceRef.current = chart
        console.log('Chart instance created')
        
        // CRITICAL: Set timezone BEFORE adding any data or series
        // TradingView Lightweight Charts requires timezone to be set early
        // Try both timezone formats to ensure compatibility
        try {
          chart.timeScale().applyOptions({
            timeZone: 'America/New_York', // Primary timezone format
            timeVisible: true,
            secondsVisible: false
          })
          // Verify timezone was actually set
          const timeScaleOptions = chart.timeScale().options()
          console.log('Chart timezone verification:', {
            requested: 'America/New_York',
            actual: timeScaleOptions.timeZone,
            timeVisible: timeScaleOptions.timeVisible
          })
          
          if (timeScaleOptions.timeZone !== 'America/New_York') {
            console.error('⚠️ WARNING: Chart timezone was NOT set correctly!', {
              expected: 'America/New_York',
              actual: timeScaleOptions.timeZone
            })
          } else {
            console.log('✓ Chart timezone successfully set to America/New_York (ET)')
          }
        } catch (e) {
          console.error('Error setting timezone to America/New_York:', e)
          // Fallback to US/Eastern if America/New_York doesn't work
          try {
            chart.timeScale().applyOptions({
              timeZone: 'US/Eastern',
              timeVisible: true,
              secondsVisible: false
            })
            const timeScaleOptions = chart.timeScale().options()
            console.log('Chart timezone set to US/Eastern (ET) - fallback', {
              actual: timeScaleOptions.timeZone
            })
          } catch (e2) {
            console.error('Failed to set chart timezone:', e2)
          }
        }
        
        // Listen for visible range changes to detect zoom out and load older data
        chart.timeScale().subscribeVisibleTimeRangeChange(async (timeRange) => {
          if (!timeRange || !timeRange.from || !timeRange.to) return
          
          const fromTimestamp = timeRange.from * 1000 // Convert to milliseconds
          const fromDate = new Date(fromTimestamp)
          const toDate = new Date(timeRange.to * 1000)
          const daysDiff = (toDate - fromDate) / (1000 * 60 * 60 * 24)
          
          console.log(`Chart visible range: ${daysDiff.toFixed(1)} days (from ${fromDate.toLocaleDateString()} to ${toDate.toLocaleDateString()})`)
          
          // Check if user zoomed out to the LEFT (older data) - need to fetch more historical data
          const loadedRange = loadedDataRangeRef.current
          if (loadedRange.earliest && fromTimestamp < loadedRange.earliest) {
            // User zoomed out to see older data - calculate how many more days needed
            const daysNeeded = Math.ceil((loadedRange.earliest - fromTimestamp) / (1000 * 60 * 60 * 24))
            const currentPeriodValue = loadedRange.periodValue || 10
            
            console.log(`🔍 Zoom out detected: fromTimestamp=${fromTimestamp}, earliest=${loadedRange.earliest}, daysNeeded=${daysNeeded}`)
            
            // Fetch more data if we need at least 1 day more (lower threshold for responsiveness)
            if (!isLoadingOlderDataRef.current && daysNeeded >= 1) {
              console.log(`🔄 Zooming out LEFT: Need ${daysNeeded} more days of historical data (currently have ${currentPeriodValue} days)`)
              isLoadingOlderDataRef.current = true
              
              try {
                // Calculate new period value (add the days needed, but respect Schwab API limit of 10 for day periodType)
                const newPeriodValue = Math.min(daysNeeded + currentPeriodValue, 10) // Cap at 10 for day periodType
                console.log(`📥 Fetching ${newPeriodValue} days of data from Schwab API...`)
                await loadOlderChartData(newPeriodValue)
              } catch (error) {
                console.error('Failed to load older chart data:', error)
              } finally {
                isLoadingOlderDataRef.current = false
              }
            } else if (isLoadingOlderDataRef.current) {
              console.log('⏳ Already loading older data, skipping...')
            } else if (daysNeeded < 1) {
              console.log(`ℹ️ Only need ${daysNeeded.toFixed(1)} days more, not fetching yet`)
            }
          } else if (!loadedRange.earliest) {
            console.log('⚠️ No earliest timestamp tracked yet, cannot determine if zoom out is needed')
          } else {
            console.log(`ℹ️ Zoom range is within loaded data: from=${fromTimestamp}, earliest=${loadedRange.earliest}`)
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
      // Parse timeframe - returns { periodValue, periodType, frequencyType, frequency }
      const { periodValue, periodType, frequencyType, frequency } = parseTimeframe(timeframe)
      
      // Always request all historical data (no view mode filtering)
      const urlParams = new URLSearchParams({
        periodType,
        periodValue: periodValue.toString(),
        frequencyType,
        frequency: frequency.toString()
      })
      
      const response = await fetch(
        `${window.location.origin}/charts/data/${selectedSymbol}?${urlParams.toString()}`
      )
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      
      // Log data received for debugging multi-day view
      console.log(`📥 Received chart data: ${data.candles?.length || 0} candles`)
      if (data.candles && data.candles.length > 0) {
        const firstTime = typeof data.candles[0].time === 'number' 
          ? new Date(data.candles[0].time) 
          : new Date(data.candles[0].time)
        const lastTime = typeof data.candles[data.candles.length - 1].time === 'number'
          ? new Date(data.candles[data.candles.length - 1].time)
          : new Date(data.candles[data.candles.length - 1].time)
        const daysDiff = (lastTime - firstTime) / (1000 * 60 * 60 * 24)
        console.log(`📥 Data spans ${daysDiff.toFixed(1)} days: ${firstTime.toLocaleDateString()} to ${lastTime.toLocaleDateString()}`)
        console.log(`📥 Should show all ${data.candles.length} candles when zoomed out`)
        
        // Update loaded data range tracking
        const firstTimestamp = firstTime.getTime()
        const lastTimestamp = lastTime.getTime()
        loadedDataRangeRef.current = {
          earliest: firstTimestamp,
          latest: lastTimestamp,
          periodValue: periodValue
        }
        console.log(`📊 Loaded data range: ${firstTime.toLocaleDateString()} to ${lastTime.toLocaleDateString()} (${periodValue} days)`)
      } else {
        console.warn(`⚠️ No candles received in chart data!`)
      }
      
      setChartData(data)
    } catch (err) {
      console.error('Failed to load chart data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const parseTimeframe = (tf) => {
    // Returns { periodValue, periodType, frequencyType, frequency }
    // Schwab API: frequencyType 'minute' supports 1,5,15,30 (NOT 60); 'daily' supports frequency=1
    switch (tf) {
      case '1min':
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 1 }
      case '2min':
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 1 }
      case '5min':
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 5 }
      case '15min':
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 15 }
      case '30min':
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 30 }
      case '1hour':
        // Schwab doesn't support 60min - use 30min (2 bars per hour)
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 30 }
      case '1day':
        // Daily bars: need 10 months for 200+ bars (MM200)
        return { periodValue: 10, periodType: 'month', frequencyType: 'daily', frequency: 1 }
      default:
        return { periodValue: 10, periodType: 'day', frequencyType: 'minute', frequency: 1 }
    }
  }
  
  // Load older historical data when user zooms out
  const loadOlderChartData = async (newPeriodValue) => {
    if (!selectedSymbol || isLoadingOlderDataRef.current) return
    
    // Validate that symbol is in watchlist
    if (watchlist.length > 0 && !watchlist.includes(selectedSymbol.toUpperCase())) {
      console.warn(`Symbol ${selectedSymbol} is not in TRADING_WATCHLIST, skipping older data load`)
      return
    }
    
    // IMPORTANT: Schwab API limits period to max 10 when periodType=day
    // When zooming out to the left, we need to fetch older data
    // Strategy: Use month periodType to get more historical data
    const { periodType, frequencyType, frequency } = parseTimeframe(timeframe)
    let actualPeriodValue = newPeriodValue
    let actualPeriodType = periodType
    
    // If requesting more than 10 days for day periodType, switch to month
    if (periodType === 'day' && newPeriodValue > 10) {
      // Convert days to months (approximate: 1 month ≈ 20 trading days)
      // Request enough months to cover the needed days
      actualPeriodType = 'month'
      actualPeriodValue = Math.max(1, Math.ceil(newPeriodValue / 20))
      console.log(`📅 Requested ${newPeriodValue} days exceeds Schwab API limit (10 days for day). Using ${actualPeriodValue} month(s) to get older data.`)
    } else if (periodType === 'day') {
      // For day periodType, cap at 10 (Schwab API limit)
      actualPeriodValue = Math.min(newPeriodValue, 10)
      if (newPeriodValue > 10) {
        console.log(`⚠️ Capping period to 10 days (Schwab API limit for periodType=day)`)
      }
    }
    
    console.log(`🔄 Loading older historical data: ${actualPeriodValue} ${actualPeriodType}(s)`)
    setLoading(true)
    
    try {
      // Request more historical data
      const urlParams = new URLSearchParams({
        periodType: actualPeriodType,
        periodValue: actualPeriodValue.toString(),
        frequencyType,
        frequency: frequency.toString()
      })
      
      const response = await fetch(
        `${window.location.origin}/charts/data/${selectedSymbol}?${urlParams.toString()}`
      )
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const newData = await response.json()
      
      if (!newData.candles || newData.candles.length === 0) {
        console.warn('⚠️ No older data received')
        return
      }
      
      // Merge with existing data
      const currentData = chartData
      if (!currentData || !currentData.candles || currentData.candles.length === 0) {
        // No existing data, just use new data
        setChartData(newData)
        return
      }
      
      // Combine candles, removing duplicates and sorting by time
      const existingCandles = currentData.candles || []
      const newCandles = newData.candles || []
      
      // Create a map to deduplicate by timestamp
      const candleMap = new Map()
      
      // Add existing candles
      existingCandles.forEach(candle => {
        const time = typeof candle.time === 'number' ? candle.time : new Date(candle.time).getTime()
        candleMap.set(time, candle)
      })
      
      // Add new candles (older ones will overwrite if there are duplicates)
      newCandles.forEach(candle => {
        const time = typeof candle.time === 'number' ? candle.time : new Date(candle.time).getTime()
        // Only add if it's older than our earliest existing candle
        const existingEarliest = loadedDataRangeRef.current.earliest
        if (!existingEarliest || time < existingEarliest) {
          candleMap.set(time, candle)
        }
      })
      
      // Convert map to sorted array
      const mergedCandles = Array.from(candleMap.values()).sort((a, b) => {
        const timeA = typeof a.time === 'number' ? a.time : new Date(a.time).getTime()
        const timeB = typeof b.time === 'number' ? b.time : new Date(b.time).getTime()
        return timeA - timeB
      })
      
      // Merge indicators (use new data's indicators as they're calculated on the full dataset)
      const mergedData = {
        ...newData,
        candles: mergedCandles
      }
      
      // Update loaded data range
      if (mergedCandles.length > 0) {
        const firstTime = typeof mergedCandles[0].time === 'number' 
          ? new Date(mergedCandles[0].time) 
          : new Date(mergedCandles[0].time)
        const lastTime = typeof mergedCandles[mergedCandles.length - 1].time === 'number'
          ? new Date(mergedCandles[mergedCandles.length - 1].time)
          : new Date(mergedCandles[mergedCandles.length - 1].time)
        
        loadedDataRangeRef.current = {
          earliest: firstTime.getTime(),
          latest: lastTime.getTime(),
          periodValue: newPeriodValue
        }
        
        console.log(`✅ Merged data: ${mergedCandles.length} candles (${existingCandles.length} existing + ${newCandles.length} new, ${mergedCandles.length - existingCandles.length - newCandles.length} duplicates removed)`)
        console.log(`📊 Updated data range: ${firstTime.toLocaleDateString()} to ${lastTime.toLocaleDateString()} (${newPeriodValue} days)`)
      }
      
      setChartData(mergedData)
    } catch (err) {
      console.error('Failed to load older chart data:', err)
      setError(err.message)
    } finally {
      setLoading(false)
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
      // Streamer sends UTC ms; chart shows "ET as UTC" (8:00–16:30) to match historical data
      const utcMs = typeof candle.time === 'number' && candle.time > 1e12 ? candle.time : candle.time * 1000
      const d = new Date(utcMs)
      const etYear = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', year: 'numeric' }), 10)
      const etMonth = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', month: 'numeric' }), 10) - 1
      const etDay = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', day: 'numeric' }), 10)
      const etHour = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', hour: '2-digit', hour12: false }), 10)
      const etMinute = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', minute: '2-digit' }), 10) || 0
      const etSecond = parseInt(d.toLocaleString('en-US', { timeZone: 'America/New_York', second: '2-digit' }), 10) || 0
      const etAsUtcDate = new Date(Date.UTC(etYear, etMonth, etDay, etHour, etMinute, etSecond))
      const timeInSeconds = Math.floor(etAsUtcDate.getTime() / 1000)
      
      // CRITICAL: Lightweight Charts throws "Cannot update oldest data" when updating with
      // a timestamp OLDER than the last bar. Only update if new candle is >= last chart candle.
      const lastTime = lastChartCandleTimeRef.current
      if (lastTime != null && timeInSeconds < lastTime) {
        console.debug(`Skipping stale real-time candle: new=${timeInSeconds} < last=${lastTime}`)
        return
      }
      
      const candleData = {
        time: timeInSeconds,
        open: parseFloat(candle.open),
        high: parseFloat(candle.high),
        low: parseFloat(candle.low),
        close: parseFloat(candle.close),
      }
      
      // Use update() for real-time updates (updates the last candle or appends new one)
      candlestickSeriesRef.current.update(candleData)
      lastChartCandleTimeRef.current = timeInSeconds
      
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
            {/* Date filter removed per requirement - real-time chart shows all data without date filter */}
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

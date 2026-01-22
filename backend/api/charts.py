"""
Chart Data API Endpoints
Provides OHLCV data and indicators for real-time charting.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, date
import pandas as pd
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request, get_valid_access_token
from core.ov_engine import OVStrategyEngine

charts_bp = Blueprint('charts', __name__, url_prefix='/charts')
logger = setup_logger("charts")

# Schwab API endpoints
SCHWAB_BASE_URL = "https://api.schwabapi.com"
SCHWAB_MARKETDATA_BASE = f"{SCHWAB_BASE_URL}/marketdata/v1"
SCHWAB_HISTORICAL_URL = f"{SCHWAB_MARKETDATA_BASE}/pricehistory"

# Initialize OV engine for indicator calculation
ov_engine = OVStrategyEngine()

@charts_bp.route('/data/<symbol>', methods=['GET'])
def get_chart_data(symbol: str):
    """
    Get chart data (OHLCV + indicators) for a symbol.
    
    Query params:
        period: 'day', 'week', 'month', 'year' (default: 'day')
        periodType: 'day', 'week', 'month', 'year' (default: 'day')
        frequencyType: 'minute', 'daily' (default: 'minute')
        frequency: 1, 5, 15, 30, 60 for minutes (default: 5)
        periodValue: number of periods (default: 1)
    
    Returns:
        JSON with candles, indicators, and metadata
    """
    try:
        # Get query parameters
        period_type = request.args.get('periodType', 'day')
        period_value = int(request.args.get('periodValue', 1))
        frequency_type = request.args.get('frequencyType', 'minute')
        frequency = int(request.args.get('frequency', 1))
        # View mode removed - always return all days with 8 AM - 4:30 PM filtering per day
        # view_mode = request.args.get('viewMode', 'today')  # No longer used
        # custom_date = request.args.get('customDate', None)  # No longer used
        
        # For MM200 calculation, we need at least 200 data points
        # After filtering to 8 AM - 4:30 PM ET, we get ~8.5 hours = ~510 minutes per day
        # For shorter timeframes, we need more days to ensure MM200 has enough data
        # Calculate minimum days needed: 200 candles / (510 minutes per day / frequency)
        # BUT: For multi-day views (lastWeek/lastMonth), don't cap - return all requested data
        if frequency_type == 'minute' and frequency > 0:
            minutes_per_day = 510  # 8 AM - 4:30 PM = ~8.5 hours = 510 minutes
            candles_per_day = minutes_per_day / frequency
            min_days_needed = max(1, int(200 / candles_per_day) + 1)  # +1 for safety margin
            if period_value < min_days_needed:
                logger.info(f"Increasing period_value from {period_value} to {min_days_needed} to ensure MM200 has enough data (frequency: {frequency}min)")
                period_value = min_days_needed
                # Cap at 20 days to ensure enough historical data for zoom out
                period_value = min(period_value, 20)
            logger.info(f"Requesting {period_value} days of data for historical chart display (allows zoom out)")
        
        # Validate frequency for minute type
        # Schwab API accepts various frequencies, but we'll use standard ones
        if frequency_type == 'minute' and frequency not in [1, 5, 15, 30, 60]:
            # Map invalid frequencies to closest valid one
            if frequency == 2:
                frequency = 1  # Map 2min to 1min
            elif frequency < 5:
                frequency = 1
            elif frequency < 15:
                frequency = 5
            elif frequency < 30:
                frequency = 15
            elif frequency < 60:
                frequency = 30
            else:
                frequency = 60
            logger.warning(f"Invalid frequency {request.args.get('frequency')} for minute type, using {frequency} instead")
        
        # Calculate date range for Schwab API
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        # Calculate end date (today)
        to_date = now_et.date()
        
        # Calculate start date based on period_value and period_type
        if period_type == 'day':
            from_date = to_date - timedelta(days=period_value - 1)  # -1 because we include today
        elif period_type == 'week':
            from_date = to_date - timedelta(weeks=period_value - 1)
        elif period_type == 'month':
            from_date = to_date - timedelta(days=30 * (period_value - 1))
        else:
            from_date = to_date - timedelta(days=period_value - 1)
        
        # Request historical data from Schwab API
        tokens = load_tokens()
        if not tokens or 'access_token' not in tokens:
            return jsonify({"error": "Not authenticated"}), 401
        
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "No valid access token available"}), 401
        
        # Build Schwab API request parameters
        params = {
            "symbol": symbol.upper(),
            "periodType": period_type,
            "period": period_value,
            "frequencyType": frequency_type,
            "frequency": frequency
        }
        
        logger.info(f"Fetching data from Schwab API for {symbol}: periodType={period_type}, period={period_value}, frequencyType={frequency_type}, frequency={frequency}")
        
        try:
            response = schwab_api_request("GET", SCHWAB_HISTORICAL_URL, access_token, params=params)
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch data from Schwab API for {symbol}: {e}")
            return jsonify({"error": f"Failed to fetch data from Schwab API: {str(e)}"}), 500
        
        if not data or 'candles' not in data:
            logger.error(f"No data returned from Schwab API for {symbol}")
            return jsonify({"error": "No data available from market data provider"}), 404
        
        candles = data['candles']
        if not candles or len(candles) == 0:
            logger.error(f"Empty candles array returned from Schwab API for {symbol}")
            return jsonify({"error": "Empty data returned from market data provider"}), 404
        
        logger.info(f"Received {len(candles)} candles from Schwab API for {symbol}")
        
        # Convert to DataFrame
        df = pd.DataFrame(candles)
        logger.info(f"Created DataFrame with {len(df)} rows. Columns: {df.columns.tolist()}")
        
        # Handle datetime column
        # Schwab API returns timestamps in milliseconds (UTC)
        import pytz
        utc = pytz.UTC
        if 'datetime' in df.columns:
            # Parse as UTC (Schwab API returns UTC timestamps)
            df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True)
        elif 'time' in df.columns:
            df['datetime'] = pd.to_datetime(df['time'], unit='ms', utc=True)
            df = df.rename(columns={'time': 'datetime'})
        else:
            logger.error(f"No datetime or time column found. Available columns: {df.columns.tolist()}")
            return jsonify({"error": "Invalid data format from market data provider"}), 500
        
        # Log raw datetime range before timezone conversion
        if len(df) > 0:
            logger.info(f"Raw datetime range (UTC): {df['datetime'].min()} to {df['datetime'].max()}")
        
        # Ensure numeric types BEFORE calculating indicators
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Calculate indicators using OV engine on FULL dataset FIRST
        # This ensures SMA200 has enough historical data (200+ candles) to calculate properly
        # We need to calculate on the full dataset, then filter to show only 8 AM - 4:30 PM
        # Check if we have enough data for MM200 (need at least 200 candles)
        if len(df) < 200:
            logger.warning(f"Only {len(df)} candles available, MM200 may not be fully calculated. Requested period: {period_value} {period_type}, frequency: {frequency}min")
        
        df = ov_engine.calculate_indicators(df)
        
        # Log indicator calculation results
        sma8_count = df['sma_8'].notna().sum() if 'sma_8' in df.columns else 0
        sma20_count = df['sma_20'].notna().sum() if 'sma_20' in df.columns else 0
        sma200_count = df['sma_200'].notna().sum() if 'sma_200' in df.columns else 0
        logger.info(f"Indicator calculation complete: {len(df)} total candles, MM8: {sma8_count}, MM20: {sma20_count}, MM200: {sma200_count} values calculated (frequency: {frequency}min)")
        
        # Now filter data to show only TODAY's data from 8:00 AM ET to 4:30 PM ET
        # Convert to ET timezone and filter
        # df['datetime'] is already UTC-aware from parsing above
        et = pytz.timezone('US/Eastern')
        df['datetime_et'] = df['datetime'].dt.tz_convert(et)
        
        # Get current time in ET timezone
        # Use pytz-aware datetime to ensure correct timezone handling
        now_et = datetime.now(et)
        current_hour = now_et.hour
        current_date = now_et.date()
        yesterday_date = (now_et - timedelta(days=1)).date()
        
        logger.info(f"Current time in ET: {now_et} (Hour: {current_hour}, Date: {current_date})")
        
        # Log available dates in the dataset
        if len(df) > 0:
            unique_dates_in_data = sorted(df['datetime_et'].dt.date.unique(), reverse=True)
            logger.info(f"Available dates in fetched data: {unique_dates_in_data}")
            logger.info(f"Data date range: {df['datetime_et'].min()} to {df['datetime_et'].max()}")
        
        # Define time range: 8:00 AM to 4:30 PM ET
        time_start = datetime.min.time().replace(hour=8, minute=0)
        time_end = datetime.min.time().replace(hour=16, minute=30)
        
        # Get today's and yesterday's time ranges
        today_start_et = et.localize(datetime.combine(current_date, time_start))
        today_end_et = et.localize(datetime.combine(current_date, time_end))
        yesterday_start_et = et.localize(datetime.combine(yesterday_date, time_start))
        yesterday_end_et = et.localize(datetime.combine(yesterday_date, time_end))
        
        logger.info(f"Today's range: {today_start_et} to {today_end_et}")
        logger.info(f"Yesterday's range: {yesterday_start_et} to {yesterday_end_et}")
        
        # Filter data for both today and yesterday (8 AM - 4:30 PM ET)
        df_today = df[
            (df['datetime_et'] >= today_start_et) &
            (df['datetime_et'] <= today_end_et)
        ].copy()
        
        df_yesterday = df[
            (df['datetime_et'] >= yesterday_start_et) &
            (df['datetime_et'] <= yesterday_end_et)
        ].copy()
        
        logger.info(f"Today's data: {len(df_today)} candles")
        logger.info(f"Yesterday's data: {len(df_yesterday)} candles")
        
        # SIMPLIFIED: Always return all days with 8 AM - 4:30 PM filtering per day
        # This allows zooming out to see historical data across multiple days
        # No view mode filtering - just return all days in the requested period
        # For today: show data up to current time (if before 4:30 PM) or up to 4:30 PM (if after)
        
        current_time_only = now_et.time()
        
        logger.info(f"Processing all days: Filtering each day to 8:00 AM - 4:30 PM ET (today up to current time), returning all {period_value} days")
        logger.info(f"Total candles fetched from API: {len(df)}")
        logger.info(f"Current time in ET: {now_et} (Hour: {current_hour}, Date: {current_date})")
        
        if len(df) > 0:
            unique_dates = sorted(df['datetime_et'].dt.date.unique())
            logger.info(f"Unique dates in fetched data: {unique_dates} (total: {len(unique_dates)} days)")
            
            # Filter each day to 8 AM - 4:30 PM ET (or current time for today)
            df_filtered_list = []
            for date in unique_dates:
                # For today, use current time if before 4:30 PM, otherwise use 4:30 PM
                if date == current_date:
                    # Today: show up to current time (if before 4:30 PM) or 4:30 PM (if after)
                    if current_time_only <= time_end:
                        day_end_time = current_time_only  # Current time
                        logger.info(f"Today ({date}): Filtering to 8:00 AM - {day_end_time.strftime('%I:%M %p')} ET (current time)")
                    else:
                        day_end_time = time_end  # 4:30 PM
                        logger.info(f"Today ({date}): Filtering to 8:00 AM - 4:30 PM ET (after market close)")
                else:
                    # Historical days: always 8 AM - 4:30 PM
                    day_end_time = time_end
                
                day_data = df[
                    (df['datetime_et'].dt.date == date) &
                    (df['datetime_et'].dt.time >= time_start) &
                    (df['datetime_et'].dt.time <= day_end_time)
                ].copy()
                
                if len(day_data) > 0:
                    df_filtered_list.append(day_data)
                    if date == current_date:
                        logger.info(f"Today ({date}): {len(day_data)} candles (8 AM - {day_end_time.strftime('%I:%M %p')} ET)")
                    else:
                        logger.debug(f"Date {date}: {len(day_data)} candles (8 AM - 4:30 PM ET)")
                else:
                    if date == current_date:
                        logger.warning(f"Today ({date}): No data found between 8:00 AM - {day_end_time.strftime('%I:%M %p')} ET")
                    else:
                        logger.debug(f"Date {date}: No data found (8 AM - 4:30 PM ET)")
            
            if df_filtered_list:
                df_filtered = pd.concat(df_filtered_list, ignore_index=True).sort_values('datetime_et')
                logger.info(f"Returning {len(df_filtered)} candles across {len(unique_dates)} days (historical: 8 AM - 4:30 PM ET, today: up to current time)")
                date_label = f"{len(unique_dates)} days (8:00 AM - 4:30 PM ET per day, today up to current time)"
            else:
                logger.warning("No data found for any day in the requested period")
                df_filtered = pd.DataFrame()  # Empty dataframe
                date_label = "no data available"
        else:
            logger.warning("No data fetched from API")
            df_filtered = pd.DataFrame()  # Empty dataframe
            date_label = "no data available"
        
        
        # Legacy view mode handling (kept for backward compatibility, but not used)
        if False:  # Disabled - always use multi-day approach above
            # Log final target date decision
            logger.info(f"Final target date: {target_date} (current_date: {current_date}, yesterday_date: {yesterday_date})")
            logger.info(f"Session end time: {session_end_time.strftime('%I:%M %p') if session_end_time else 'all'}, Date label: {date_label}")
            
            # Get data for target date (which may have been updated by fallback logic)
            df_target = df[
                (df['datetime_et'].dt.date == target_date) &
                (df['datetime_et'].dt.time >= time_start) &
                (df['datetime_et'].dt.time <= session_end_time)
            ].copy()
            
            # Get yesterday's data for gap filling (use the day before target_date)
            target_yesterday_date = target_date - timedelta(days=1)
            df_yesterday_for_fill = df[
                (df['datetime_et'].dt.date == target_yesterday_date) &
                (df['datetime_et'].dt.time >= time_start) &
                (df['datetime_et'].dt.time <= time_end)
            ].copy()
            
            # Create a complete time series template from 8:00 AM to session_end_time
            # Use the frequency to determine time intervals
            if frequency_type == 'minute' and frequency > 0:
                # Generate all time slots for the session
                session_start_dt = et.localize(datetime.combine(target_date, time_start))
                session_end_dt = et.localize(datetime.combine(target_date, session_end_time))
            
                # Create time slots at the specified frequency
                time_slots = []
                current_slot = session_start_dt
                while current_slot <= session_end_dt:
                    time_slots.append(current_slot.time())
                    current_slot += timedelta(minutes=frequency)
                
                logger.info(f"Created {len(time_slots)} time slots from 8:00 AM to {session_end_time.strftime('%I:%M %p')} at {frequency}min intervals")
                
                # Build complete dataframe by filling each time slot
                df_complete = []
                
                for slot_time in time_slots:
                    # Try to find data for this time slot from target date
                    slot_data = df_target[df_target['datetime_et'].dt.time == slot_time]
                    
                    if len(slot_data) > 0:
                        # Use target date's data
                        df_complete.append(slot_data.iloc[0:1])
                    else:
                        # Fill with previous day's data for this time slot
                        prev_day_slot = df_yesterday_for_fill[df_yesterday_for_fill['datetime_et'].dt.time == slot_time]
                        if len(prev_day_slot) > 0:
                            # Use previous day's data but adjust the date to target_date for continuity
                            fill_row = prev_day_slot.iloc[0:1].copy()
                            # Adjust datetime_et to target_date while keeping the time
                            # This ensures the x-axis shows continuous time on the target_date
                            adjusted_datetime_et = et.localize(datetime.combine(target_date, slot_time))
                            fill_row.loc[fill_row.index[0], 'datetime_et'] = adjusted_datetime_et
                            # Also adjust the original datetime column to match
                            if 'datetime' in fill_row.columns:
                                # Convert ET datetime to UTC for the datetime column
                                # Fix pandas FutureWarning by ensuring dtype compatibility
                                utc_datetime = adjusted_datetime_et.astimezone(pytz.UTC).replace(tzinfo=None)
                                
                                # Get the existing dtype of the datetime column
                                existing_dtype = fill_row['datetime'].dtype
                                
                                # Convert to match the existing dtype
                                if 'UTC' in str(existing_dtype) or 'timezone' in str(existing_dtype).lower():
                                    # Column is timezone-aware, keep it timezone-aware
                                    utc_timestamp = pd.Timestamp(utc_datetime, tz='UTC')
                                    fill_row.loc[fill_row.index[0], 'datetime'] = utc_timestamp
                                else:
                                    # Column is naive, convert to naive timestamp
                                    naive_timestamp = pd.Timestamp(utc_datetime)
                                    # Explicitly cast to match existing dtype
                                    fill_row['datetime'] = fill_row['datetime'].astype('datetime64[ns]')
                                    fill_row.loc[fill_row.index[0], 'datetime'] = naive_timestamp
                            df_complete.append(fill_row)
                            logger.debug(f"Filled {slot_time.strftime('%I:%M %p')} with previous day's data")
                        # If no previous day data either, skip this slot (shouldn't happen if we have enough historical data)
                
                if df_complete:
                    df_filtered = pd.concat(df_complete, ignore_index=True).sort_values('datetime_et')
                    logger.info(f"Created complete time series with {len(df_filtered)} candles (no gaps) for {date_label}")
                else:
                    # Final fallback: return error
                    unique_dates = df['datetime_et'].dt.date.unique() if len(df) > 0 else []
                    date_range = (df['datetime_et'].min(), df['datetime_et'].max()) if len(df) > 0 else (None, None)
                    logger.error(f"Failed to create time series. Target: {target_date}, Available dates: {unique_dates}")
                    return jsonify({
                        "error": f"No data available for {date_label} ({target_date}) between 8:00 AM ET and {session_end_time.strftime('%I:%M %p')} ET",
                        "available_dates": [str(d) for d in unique_dates],
                        "date_range": {"min": str(date_range[0]) if date_range[0] else None, "max": str(date_range[1]) if date_range[1] else None},
                        "total_candles": len(df) if len(df) > 0 else 0
                    }), 404
            else:
                # Non-minute frequency - use simpler approach (fallback)
                logger.warning(f"Non-minute frequency ({frequency_type}), using fallback approach")
                if current_hour < 8:
                    df_filtered = df_yesterday.copy()
                elif current_time_only <= time_end:
                    df_filtered = df_today[
                        (df_today['datetime_et'] >= today_start_et) &
                        (df_today['datetime_et'] <= now_et)
                    ].copy()
                else:
                    df_filtered = df_today.copy()
                
                if len(df_filtered) == 0:
                    df_filtered = df_yesterday.copy()
        
        # Log date range of filtered data
        if len(df_filtered) > 0:
            min_date = df_filtered['datetime_et'].min()
            max_date = df_filtered['datetime_et'].max()
            unique_dates = df_filtered['datetime_et'].dt.date.unique()
            logger.info(f"Filtered data: {len(df_filtered)} candles from {min_date} to {max_date}. Unique dates: {unique_dates}")
        
        # Use filtered dataframe
        df = df_filtered
        
        # Log the actual time range of filtered data
        if len(df) > 0:
            min_time_et = df['datetime_et'].min()
            max_time_et = df['datetime_et'].max()
            unique_dates_final = df['datetime_et'].dt.date.unique()
            logger.info(f"Final filtered data: {len(df)} candles, Date(s): {unique_dates_final}, Time range: {min_time_et} to {max_time_et} ET")
        
        # Convert to chart-friendly format
        chart_data = {
            'symbol': symbol.upper(),
            'candles': [],
            'indicators': {
                'sma_8': [],
                'sma_20': [],
                'sma_200': [],
                'rsi_14': [],
                'volume': []
            },
            'metadata': {
                'period_type': period_type,
                'frequency': frequency,
                'total_candles': len(df),
                'last_update': datetime.now().isoformat()
            }
        }
        
        # Format candles and indicators
        # CRITICAL: Lightweight Charts does NOT support timezone conversion natively
        # We must manually adjust timestamps to ET timezone BEFORE sending to the chart
        # The chart library processes all timestamps in UTC, so we need to convert ET times
        # to appear as if they were UTC times (by subtracting the ET offset)
        for idx, row in df.iterrows():
            # Use datetime_et (ET timezone) for the timestamp
            # Since Lightweight Charts doesn't support timezone, we need to adjust the timestamp
            # to make ET times display correctly. We do this by converting ET to UTC timestamp,
            # but then adjusting it back so the chart displays it as ET time
            if 'datetime_et' in row and pd.notna(row['datetime_et']):
                # CRITICAL FIX: Lightweight Charts doesn't support timezone conversion natively
                # We must manually adjust timestamps so ET times display correctly
                # Solution: Create a timestamp that represents ET time as if it were UTC
                # This way, when the chart displays it as UTC, it shows the ET time
                et_dt = row['datetime_et']
                # Get the ET offset (ET is UTC-5 or UTC-4 depending on DST)
                utc_dt = et_dt.astimezone(pytz.UTC)
                # Calculate offset: how many hours ahead UTC is compared to ET
                et_offset_hours = (utc_dt.hour - et_dt.hour) % 24
                if et_offset_hours > 12:
                    et_offset_hours -= 24
                # Create a naive datetime with ET time values (treat as UTC for display)
                naive_dt_et_as_utc = datetime(
                    et_dt.year, et_dt.month, et_dt.day,
                    et_dt.hour, et_dt.minute, et_dt.second
                )
                # Convert to timestamp - this will display as ET time in the chart
                et_timestamp = int(pd.Timestamp(naive_dt_et_as_utc).timestamp() * 1000)
            elif 'datetime' in row and pd.notna(row['datetime']):
                # Fallback: if datetime is timezone-aware, use it directly
                # If naive, assume it's UTC (from Schwab API)
                if hasattr(row['datetime'], 'tz') and row['datetime'].tz is not None:
                    et_timestamp = int(row['datetime'].timestamp() * 1000)
                else:
                    # Naive datetime - assume UTC from Schwab API
                    import pytz
                    utc = pytz.UTC
                    dt_utc = utc.localize(row['datetime']) if row['datetime'].tz is None else row['datetime']
                    et_timestamp = int(dt_utc.timestamp() * 1000)
            else:
                logger.warning(f"Missing datetime for candle at index {idx}")
                et_timestamp = None
            
            candle = {
                'time': et_timestamp,
                'open': float(row['open']) if pd.notna(row.get('open')) else None,
                'high': float(row['high']) if pd.notna(row.get('high')) else None,
                'low': float(row['low']) if pd.notna(row.get('low')) else None,
                'close': float(row['close']) if pd.notna(row.get('close')) else None,
                'volume': float(row['volume']) if pd.notna(row.get('volume')) else None
            }
            chart_data['candles'].append(candle)
            
            # Add indicators (use same adjusted timestamp for proper alignment)
            if 'sma_8' in row and pd.notna(row['sma_8']):
                chart_data['indicators']['sma_8'].append({
                    'time': et_timestamp,
                    'value': float(row['sma_8'])
                })
            
            if 'sma_20' in row and pd.notna(row['sma_20']):
                chart_data['indicators']['sma_20'].append({
                    'time': et_timestamp,
                    'value': float(row['sma_20'])
                })
            
            # Always include MM200 if it exists and is valid
            # MM200 needs 200 candles, so early candles will have NaN values
            if 'sma_200' in row:
                if pd.notna(row['sma_200']):
                    chart_data['indicators']['sma_200'].append({
                        'time': et_timestamp,
                        'value': float(row['sma_200'])
                    })
                # If MM200 is NaN, skip it (expected for first ~200 candles)
            
            if 'rsi_14' in row and pd.notna(row['rsi_14']):
                chart_data['indicators']['rsi_14'].append({
                    'time': et_timestamp,
                    'value': float(row['rsi_14'])
                })
        
        logger.info(f"Chart data retrieved for {symbol}: {len(chart_data['candles'])} candles")
        
        # Log summary for all days returned
        if len(chart_data['candles']) > 0:
            first_candle_time = chart_data['candles'][0]['time']
            last_candle_time = chart_data['candles'][-1]['time']
            first_date = datetime.fromtimestamp(first_candle_time / 1000)
            last_date = datetime.fromtimestamp(last_candle_time / 1000)
            days_span = (last_date - first_date).days + 1
            logger.info(f"Chart data summary: {len(chart_data['candles'])} candles spanning {days_span} days ({first_date.date()} to {last_date.date()})")
        else:
            logger.warning(f"Chart returned 0 candles - check if data is available for {symbol}")
        
        return jsonify(chart_data), 200
        
    except Exception as e:
        logger.error(f"Failed to get chart data for {symbol}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@charts_bp.route('/watchlist', methods=['GET'])
def get_watchlist():
    """
    Get trading watchlist from TRADING_WATCHLIST environment variable.
    
    Returns:
        JSON with watchlist array
    """
    try:
        import os
        from dotenv import load_dotenv
        
        # Ensure .env is loaded (in case it wasn't loaded at startup)
        load_dotenv()
        
        watchlist_str = os.getenv("TRADING_WATCHLIST", "")
        
        if not watchlist_str:
            logger.warning("TRADING_WATCHLIST not found in environment, using empty list")
            return jsonify({
                "watchlist": []
            }), 200
        
        watchlist = [s.strip().upper() for s in watchlist_str.split(",") if s.strip()]
        
        logger.info(f"Watchlist loaded from TRADING_WATCHLIST env: {watchlist}")
        return jsonify({
            "watchlist": watchlist
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}")
        return jsonify({
            "error": str(e),
            "watchlist": []
        }), 500

@charts_bp.route('/setup/<symbol>', methods=['GET'])
def get_chart_with_setup(symbol: str):
    """
    Get chart data with current setup analysis (if any).
    Includes entry/stop/target levels from AI analysis.
    """
    try:
        # Get basic chart data
        chart_response = get_chart_data(symbol)
        if chart_response[1] != 200:
            return chart_response
        
        chart_data = chart_response[0].get_json()
        
        # Try to get current setup from scheduler (if available)
        try:
            from api.automation import scheduler
            if scheduler and scheduler.is_running:
                # Get latest setup for this symbol
                # This would require storing recent setups - for now return basic data
                pass
        except:
            pass
        
        return jsonify(chart_data), 200
        
    except Exception as e:
        logger.error(f"Failed to get chart with setup for {symbol}: {e}")
        return jsonify({"error": str(e)}), 500


"""
Chart Data API Endpoints
Provides OHLCV data and indicators for real-time charting.
"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, date, timezone
import pandas as pd
from utils.logger import setup_logger
from utils.helpers import load_tokens, schwab_api_request, get_valid_access_token
from core.ov_engine import OVStrategyEngine
# Import Streamer real-time data
from api.streaming import latest_chart_data

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
        logger.info(f"Chart data request for {symbol}")
        # Get query parameters
        period_type = request.args.get('periodType', 'day')
        period_value = int(request.args.get('periodValue', 1))
        frequency_type = request.args.get('frequencyType', 'minute')
        frequency = int(request.args.get('frequency', 1))
        # View mode removed - always return all days with 8 AM - 4:30 PM filtering per day
        # view_mode = request.args.get('viewMode', 'today')  # No longer used
        # custom_date = request.args.get('customDate', None)  # No longer used
        
        # IMPORTANT: Schwab API limits period values when periodType=day
        # Valid values for periodType=day: [1, 2, 3, 4, 5, 10]
        # We must cap period_value to 10 for day periodType
        if period_type == 'day':
            if period_value > 10:
                logger.warning(f"period_value {period_value} exceeds Schwab API limit for periodType=day (max 10). Capping to 10.")
                period_value = 10
            elif period_value not in [1, 2, 3, 4, 5, 10]:
                # Round to nearest valid value
                valid_periods = [1, 2, 3, 4, 5, 10]
                period_value = min(valid_periods, key=lambda x: abs(x - period_value))
                logger.warning(f"period_value adjusted to nearest valid value: {period_value}")
        
        # For MM200 calculation, we need at least 200 data points
        # After filtering to 8 AM - 4:30 PM ET, we get ~8.5 hours = ~510 minutes per day
        # For shorter timeframes, we need more days to ensure MM200 has enough data
        # Calculate minimum days needed: 200 candles / (510 minutes per day / frequency)
        if frequency_type == 'minute' and frequency > 0:
            minutes_per_day = 510  # 8 AM - 4:30 PM = ~8.5 hours = 510 minutes
            candles_per_day = minutes_per_day / frequency
            min_days_needed = max(1, int(200 / candles_per_day) + 1)  # +1 for safety margin
            if min_days_needed > 10:
                # Need more than 10 days for MM200 - switch to month (Schwab day max is 10)
                period_type = 'month'
                period_value = max(1, (min_days_needed + 9) // 21)  # ~21 trading days per month
                logger.info(f"Switching to periodType=month, period={period_value} for MM200 warmup (need {min_days_needed} days, frequency: {frequency}min)")
            elif period_value < min_days_needed:
                logger.info(f"Increasing period_value from {period_value} to {min_days_needed} to ensure MM200 has enough data (frequency: {frequency}min)")
                period_value = min(min_days_needed, 10)  # Cap at 10 (Schwab API limit for day)
            logger.info(f"Requesting {period_value} {period_type}(s) of data for historical chart display")
        elif frequency_type == 'daily':
            # For daily: need 200+ bars for MM200. ~21 trading days per month.
            # Request extra months for warmup so MM200 extends from left edge
            min_months_for_mm200 = max(1, 200 // 21 + 1)  # ~10 months for 200 bars
            if period_type == 'month' and period_value < min_months_for_mm200 * 2:
                # Request 2x to have warmup (trim first 200 bars before returning)
                requested_months = min(20, max(period_value * 2, min_months_for_mm200 * 2))
                logger.info(f"Increasing period_value from {period_value} to {requested_months} months for daily MM200 warmup")
                period_value = requested_months
        
        # Validate frequency for minute type (Schwab does NOT support frequency=60)
        if frequency_type == 'minute' and frequency not in [1, 5, 15, 30]:
            # Map invalid frequencies to closest valid one (Schwab supports 1,5,15,30 only - no 60)
            if frequency == 2:
                frequency = 1  # Map 2min to 1min
            elif frequency < 5:
                frequency = 1
            elif frequency < 15:
                frequency = 5
            else:
                frequency = 30  # 60 and higher map to 30min
            logger.warning(f"Invalid frequency {request.args.get('frequency')} for minute type, using {frequency} instead")
        
        # Calculate date range for Schwab API
        import pytz
        et = pytz.timezone('US/Eastern')
        now_et = datetime.now(et)
        
        # Calculate end date (today)
        to_date = now_et.date()
        
        # Calculate start date based on period_value and period_type
        # IMPORTANT: Schwab API period=10 with periodType=day means "last 10 days including today"
        # So we need to go back (period_value - 1) days to include today
        if period_type == 'day':
            from_date = to_date - timedelta(days=period_value - 1)  # -1 because we include today
        elif period_type == 'week':
            from_date = to_date - timedelta(weeks=period_value - 1)
        elif period_type == 'month':
            from_date = to_date - timedelta(days=30 * (period_value - 1))
        else:
            from_date = to_date - timedelta(days=period_value - 1)
        
        logger.info(f"Requesting data from {from_date} to {to_date} (period={period_value}, periodType={period_type})")
        
        # Request historical data from Schwab API
        tokens = load_tokens()
        if not tokens or 'access_token' not in tokens:
            return jsonify({"error": "Not authenticated"}), 401
        
        access_token = get_valid_access_token()
        if not access_token:
            return jsonify({"error": "No valid access token available"}), 401
        
        # Build Schwab API request parameters
        # CRITICAL: Add startDate/endDate in milliseconds to explicitly include TODAY
        # Schwab API may omit today when using only period/periodType; explicit dates force inclusion
        from_start = et.localize(datetime.combine(from_date, datetime.min.time()))
        to_end = et.localize(datetime.combine(to_date, datetime.max.time()))
        start_ms = int(from_start.timestamp() * 1000)
        end_ms = int(to_end.timestamp() * 1000)
        
        params = {
            "symbol": symbol.upper(),
            "periodType": period_type,
            "period": period_value,
            "frequencyType": frequency_type,
            "frequency": frequency,
            "startDate": start_ms,
            "endDate": end_ms,
        }
        
        logger.info(f"Fetching data from Schwab API for {symbol}: periodType={period_type}, period={period_value}, startDate={from_date}, endDate={to_date} (explicit dates to include today)")
        
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
        
        # Convert to ET timezone BEFORE combining with Streamer data
        # df['datetime'] is already UTC-aware from parsing above
        et = pytz.timezone('US/Eastern')
        df['datetime_et'] = df['datetime'].dt.tz_convert(et)
        
        # CRITICAL: Combine with Streamer real-time data for today BEFORE filtering
        # (Skip for daily frequency - Streamer is intraday only)
        symbol_upper = symbol.upper()
        streamer_candles_added = 0
        if frequency_type != 'daily' and symbol_upper in latest_chart_data:
            streamer_candle = latest_chart_data[symbol_upper]
            logger.info(f"🔴 Found Streamer real-time data for {symbol_upper}: {streamer_candle}")
            
            # Convert Streamer candle to DataFrame row format
            if streamer_candle.get('time') and streamer_candle.get('close'):
                streamer_time_ms = streamer_candle.get('time')
                streamer_dt_utc = pd.to_datetime(streamer_time_ms, unit='ms', utc=True)
                streamer_dt_et = streamer_dt_utc.tz_convert(et)
                
                # Get current date in ET
                now_et = datetime.now(et)
                current_date = now_et.date()
                
                # Check if this is today's data
                if streamer_dt_et.date() == current_date:
                    logger.info(f"✅ Streamer candle is from today: {streamer_dt_et}")
                    
                    # Create a DataFrame row for the Streamer candle
                    streamer_row = {
                        'datetime': streamer_dt_utc,
                        'datetime_et': streamer_dt_et,
                        'open': streamer_candle.get('open') or streamer_candle.get('close'),
                        'high': streamer_candle.get('high') or streamer_candle.get('close'),
                        'low': streamer_candle.get('low') or streamer_candle.get('close'),
                        'close': streamer_candle.get('close'),
                        'volume': streamer_candle.get('volume') or 0
                    }
                    
                    # Check if we already have this candle (by time, within 1 minute)
                    existing_mask = (
                        (df['datetime_et'].dt.date == current_date) &
                        (abs((df['datetime_et'] - streamer_dt_et).dt.total_seconds()) < 60)
                    )
                    
                    if existing_mask.sum() > 0:
                        # Update existing candle with Streamer data (more recent)
                        idx = df[existing_mask].index[0]
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            if col in streamer_row and streamer_row[col] is not None:
                                df.at[idx, col] = streamer_row[col]
                        logger.info(f"🔄 Updated existing candle with Streamer data: {streamer_dt_et}")
                    else:
                        # Add Streamer candle to main df (before filtering)
                        streamer_df = pd.DataFrame([streamer_row])
                        # Ensure all columns match
                        for col in df.columns:
                            if col not in streamer_df.columns:
                                streamer_df[col] = None
                        df = pd.concat([df, streamer_df], ignore_index=True)
                        streamer_candles_added += 1
                        logger.info(f"➕ Added Streamer real-time candle to main dataframe: {streamer_dt_et}")
                else:
                    logger.debug(f"Streamer candle is not from today: {streamer_dt_et.date()} (today is {current_date})")
        else:
            logger.warning(f"⚠️ No Streamer real-time data available for {symbol_upper}. Historical API may not return today's data.")
        
        if streamer_candles_added > 0:
            logger.info(f"✅ Added {streamer_candles_added} Streamer candle(s) to historical data")
            # Re-sort by datetime_et after adding Streamer data
            df = df.sort_values('datetime_et').reset_index(drop=True)
            # Recalculate indicators for the new data
            df = ov_engine.calculate_indicators(df)
        
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
        
        logger.info(f"Today's data from historical API: {len(df_today)} candles")
        logger.info(f"Yesterday's data: {len(df_yesterday)} candles")
        
        # SIMPLIFIED: Always return all days with 8 AM - 4:30 PM filtering per day
        # This allows zooming out to see historical data across multiple days
        # No view mode filtering - just return all days in the requested period
        # For today: show data up to current time (if before 4:30 PM) or up to 4:30 PM (if after)
        
        current_time_only = now_et.time()
        
        logger.info(f"Processing all days: Filtering each day to 8:00 AM - 4:30 PM ET (today up to current time), returning all {period_value} days")
        logger.info(f"Total candles fetched from API: {len(df)}")
        logger.info(f"Current time in ET: {now_et} (Hour: {current_hour}, Date: {current_date})")
        
        if frequency_type == 'daily':
            # Daily frequency: no intraday filtering - 1 bar per day, use data as-is
            df_filtered = df.sort_values('datetime_et').copy() if len(df) > 0 else pd.DataFrame()
            date_label = f"{len(df_filtered)} daily bars" if len(df_filtered) > 0 else "no data available"
            logger.info(f"Daily frequency: using {len(df_filtered)} bars as-is (no 8AM-4:30PM filter)")
        elif len(df) > 0:
            unique_dates = sorted(df['datetime_et'].dt.date.unique())
            logger.info(f"Unique dates in fetched data: {unique_dates} (total: {len(unique_dates)} days)")
            logger.info(f"Current date (ET): {current_date}")
            logger.info(f"Is today in fetched data? {current_date in unique_dates}")
            
            # CRITICAL: Check if today's data exists in the raw data BEFORE any filtering
            today_raw_data = df[df['datetime_et'].dt.date == current_date].copy()
            logger.info(f"🔍 Raw today's data (before ANY filtering): {len(today_raw_data)} candles")
            if len(today_raw_data) > 0:
                logger.info(f"  Today's data time range: {today_raw_data['datetime_et'].min()} to {today_raw_data['datetime_et'].max()}")
                logger.info(f"  Today's data times: {sorted(today_raw_data['datetime_et'].dt.time.unique())[:10]}...")  # Show first 10 unique times
            else:
                logger.error(f"❌ NO DATA FOUND FOR TODAY ({current_date})!")
                logger.error(f"  Available dates: {unique_dates}")
                logger.error(f"  Data date range: {df['datetime_et'].min()} to {df['datetime_et'].max()}")
            
            # Filter each day to 8 AM - 4:30 PM ET
            # CRITICAL: For today, ALWAYS include ALL data regardless of time
            df_filtered_list = []
            today_included = False
            
            for date in unique_dates:
                if date == current_date:
                    # TODAY: Include ALL data for today, NO time filtering
                    today_all_data = df[df['datetime_et'].dt.date == current_date].copy()
                    if len(today_all_data) > 0:
                        logger.info(f"✅ Today ({date}): Including ALL {len(today_all_data)} candles (NO time filtering)")
                        logger.info(f"  Today's data time range: {today_all_data['datetime_et'].min()} to {today_all_data['datetime_et'].max()}")
                        df_filtered_list.append(today_all_data)
                        today_included = True
                    else:
                        logger.error(f"❌ Today ({date}): No data found even though date is in unique_dates!")
                else:
                    # Historical days: filter to 8 AM - 4:30 PM ET
                    day_data = df[
                        (df['datetime_et'].dt.date == date) &
                        (df['datetime_et'].dt.time >= time_start) &
                        (df['datetime_et'].dt.time <= time_end)
                    ].copy()
                    
                    if len(day_data) > 0:
                        df_filtered_list.append(day_data)
                        logger.debug(f"Date {date}: {len(day_data)} candles (8 AM - 4:30 PM ET)")
                    else:
                        logger.debug(f"Date {date}: No data found (8 AM - 4:30 PM ET)")
            
            # CRITICAL FALLBACK: If today is NOT in unique_dates but exists in data, add it
            if not today_included:
                today_check = df[df['datetime_et'].dt.date == current_date].copy()
                if len(today_check) > 0:
                    logger.error(f"⚠️ Today ({current_date}) was NOT in unique_dates but found {len(today_check)} candles - FORCING inclusion")
                    logger.error(f"  Today's data time range: {today_check['datetime_et'].min()} to {today_check['datetime_et'].max()}")
                    df_filtered_list.append(today_check)
                    today_included = True
                else:
                    logger.error(f"❌ Today ({current_date}) has NO data in the API response!")
                    logger.error(f"  This might mean: market hasn't opened yet, it's a weekend/holiday, or API doesn't return today's data")
            
            if df_filtered_list:
                df_filtered = pd.concat(df_filtered_list, ignore_index=True).sort_values('datetime_et')
                
                # CRITICAL: Verify today's data is in the final result
                today_in_final = df_filtered[df_filtered['datetime_et'].dt.date == current_date]
                if len(today_in_final) > 0:
                    logger.info(f"✅ VERIFIED: Today's data is in final result: {len(today_in_final)} candles")
                    logger.info(f"  Today's final time range: {today_in_final['datetime_et'].min()} to {today_in_final['datetime_et'].max()}")
                else:
                    logger.error(f"❌ ERROR: Today's data is MISSING from final result!")
                    logger.error(f"  Final data date range: {df_filtered['datetime_et'].min()} to {df_filtered['datetime_et'].max()}")
                    logger.error(f"  Final unique dates: {sorted(df_filtered['datetime_et'].dt.date.unique())}")
                    # Force include today's data if it exists in raw data
                    if len(today_raw_data) > 0:
                        logger.error(f"  FORCING today's data into final result...")
                        df_filtered = pd.concat([df_filtered, today_raw_data], ignore_index=True).sort_values('datetime_et')
                        logger.info(f"  After force-include: {len(df_filtered)} candles, today: {len(df_filtered[df_filtered['datetime_et'].dt.date == current_date])} candles")
                
                logger.info(f"Returning {len(df_filtered)} candles across {len(df_filtered['datetime_et'].dt.date.unique())} days")
                final_dates = sorted(df_filtered['datetime_et'].dt.date.unique())
                logger.info(f"Final dates in result: {final_dates}")
                date_label = f"{len(final_dates)} days (8:00 AM - 4:30 PM ET per day, today: all available data)"
            else:
                logger.warning("No data found for any day in the requested period")
                df_filtered = pd.DataFrame()  # Empty dataframe
                date_label = "no data available"
        else:
            logger.warning("No data fetched from API")
            df_filtered = pd.DataFrame()  # Empty dataframe
            date_label = "no data available"
        
        # MM200 warmup: trim first 200 rows so MM200 extends from left edge of chart
        # (SMA200 needs 200 bars; first 199 are NaN - by trimming we start display where MM200 has values)
        if len(df_filtered) > 200 and 'sma_200' in df_filtered.columns:
            warmup = 200
            before = len(df_filtered)
            df_filtered = df_filtered.iloc[warmup:].reset_index(drop=True)
            logger.info(f"MM200 warmup: trimmed first {warmup} bars, returning {len(df_filtered)} (was {before})")
        
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
                # CRITICAL: Lightweight Charts displays timestamps as UTC and timeZone option doesn't work.
                # Send timestamps that, when shown as UTC, display ET clock times (8:00–16:30).
                # Build a naive datetime from ET components, treat it as UTC, then take timestamp.
                et_dt = row['datetime_et']
                naive_et_as_utc = datetime(
                    et_dt.year, et_dt.month, et_dt.day,
                    et_dt.hour, et_dt.minute, et_dt.second
                )
                # Treat as UTC so chart's UTC display shows 8:00, 9:00, ... 16:30 (ET times)
                et_timestamp = int(naive_et_as_utc.replace(tzinfo=timezone.utc).timestamp() * 1000)
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
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Failed to get chart data for {symbol}: {e}\n{error_trace}")
        return jsonify({
            "error": f"Failed to get chart data: {str(e)}",
            "symbol": symbol,
            "details": str(e)
        }), 500

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


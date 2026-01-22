"""
Enhanced Chart Renderer for Market Data
Generates charts with EMA 20, EMA 200, VWAP, and volume.
Stores charts with deterministic filenames: SYMBOL_TIMEFRAME_YYYYMMDD_HHMM.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from io import BytesIO
import base64
from utils.logger import setup_logger
from utils.market_data_db import store_chart_metadata

logger = setup_logger("chart_renderer")

# Chart storage directory
CHARTS_DIR = Path("data/charts")
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

def generate_chart_image(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    timestamp: Optional[int] = None,
    save_to_disk: bool = True
) -> Optional[str]:
    """
    Generate chart image with candlesticks, EMA 20, EMA 200, VWAP, and volume.
    
    Args:
        df: DataFrame with OHLCV data and indicators (must have datetime index)
        symbol: Stock symbol
        timeframe: Timeframe ('1min', '5min', 'daily')
        timestamp: Unix timestamp in milliseconds (for filename)
        save_to_disk: Whether to save chart to disk
        
    Returns:
        Base64 encoded image string or filepath
    """
    try:
        if df.empty or len(df) < 20:
            logger.warning(f"Insufficient data for chart: {len(df)} candles")
            return None
        
        # Use last 100 candles for clarity
        chart_df = df.tail(100).copy()
        
        # Ensure datetime index
        if not isinstance(chart_df.index, pd.DatetimeIndex):
            if 'datetime' in chart_df.columns:
                chart_df.set_index('datetime', inplace=True)
            elif 'timestamp' in chart_df.columns:
                chart_df['datetime'] = pd.to_datetime(chart_df['timestamp'], unit='ms')
                chart_df.set_index('datetime', inplace=True)
            else:
                logger.error("DataFrame must have datetime index")
                return None
        
        # Create figure with subplots
        fig = plt.figure(figsize=(14, 10), facecolor='#1a1a1a')
        gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 0.5], hspace=0.3)
        
        # Main price chart
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('#0f0f0f')
        
        # Plot candlesticks
        for idx, row in chart_df.iterrows():
            color = '#22c55e' if row['close'] >= row['open'] else '#ef4444'  # Green/Red
            body_height = abs(row['close'] - row['open'])
            wick_top = max(row['close'], row['open'])
            wick_bottom = min(row['close'], row['open'])
            
            # Candle body
            rect = Rectangle(
                (mdates.date2num(idx) - 0.2, min(row['close'], row['open'])),
                0.4,
                body_height if body_height > 0 else 0.01,
                facecolor=color,
                edgecolor=color,
                linewidth=0.5
            )
            ax1.add_patch(rect)
            
            # Wicks
            ax1.plot(
                [mdates.date2num(idx), mdates.date2num(idx)],
                [row['low'], wick_bottom],
                color=color,
                linewidth=0.8
            )
            ax1.plot(
                [mdates.date2num(idx), mdates.date2num(idx)],
                [wick_top, row['high']],
                color=color,
                linewidth=0.8
            )
        
        # Plot EMA 20 (yellow/gold)
        if 'ema_20' in chart_df.columns:
            ema_20_data = chart_df['ema_20'].dropna()
            if not ema_20_data.empty:
                ax1.plot(
                    mdates.date2num(ema_20_data.index),
                    ema_20_data.values,
                    color='#fbbf24',  # Gold/Yellow
                    linewidth=2,
                    label='EMA 20',
                    alpha=0.9
                )
        
        # Plot EMA 200 (blue)
        if 'ema_200' in chart_df.columns:
            ema_200_data = chart_df['ema_200'].dropna()
            if not ema_200_data.empty:
                ax1.plot(
                    mdates.date2num(ema_200_data.index),
                    ema_200_data.values,
                    color='#3b82f6',  # Blue
                    linewidth=2,
                    label='EMA 200',
                    alpha=0.9
                )
        
        # Plot VWAP (cyan)
        if 'vwap' in chart_df.columns:
            vwap_data = chart_df['vwap'].dropna()
            if not vwap_data.empty:
                ax1.plot(
                    mdates.date2num(vwap_data.index),
                    vwap_data.values,
                    color='#06b6d4',  # Cyan
                    linewidth=2,
                    label='VWAP',
                    alpha=0.8,
                    linestyle='--'
                )
        
        ax1.set_ylabel('Price', color='#9ca3af', fontsize=10)
        ax1.tick_params(colors='#9ca3af')
        ax1.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='#2a2f4a', labelcolor='#9ca3af')
        ax1.grid(True, alpha=0.2, color='#2a2f4a')
        ax1.spines['bottom'].set_color('#2a2f4a')
        ax1.spines['top'].set_color('#2a2f4a')
        ax1.spines['right'].set_color('#2a2f4a')
        ax1.spines['left'].set_color('#2a2f4a')
        
        # Volume chart
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        ax2.set_facecolor('#0f0f0f')
        
        if 'volume' in chart_df.columns:
            for idx, row in chart_df.iterrows():
                color = '#22c55e' if row['close'] >= row['open'] else '#ef4444'
                ax2.bar(
                    mdates.date2num(idx),
                    row['volume'],
                    width=0.4,
                    color=color,
                    alpha=0.6
                )
        
        ax2.set_ylabel('Volume', color='#9ca3af', fontsize=10)
        ax2.tick_params(colors='#9ca3af')
        ax2.grid(True, alpha=0.2, color='#2a2f4a')
        ax2.spines['bottom'].set_color('#2a2f4a')
        ax2.spines['top'].set_color('#2a2f4a')
        ax2.spines['right'].set_color('#2a2f4a')
        ax2.spines['left'].set_color('#2a2f4a')
        
        # Format x-axis
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax2.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Title
        fig.suptitle(
            f'{symbol} - {timeframe.upper()}',
            color='#9ca3af',
            fontsize=14,
            fontweight='bold',
            y=0.98
        )
        
        # Add timestamp
        if timestamp:
            dt = datetime.fromtimestamp(timestamp / 1000)
            fig.text(
                0.99, 0.01,
                f'Generated: {dt.strftime("%Y-%m-%d %H:%M:%S")}',
                ha='right',
                va='bottom',
                color='#6b7280',
                fontsize=8
            )
        
        plt.tight_layout()
        
        # Save to BytesIO for base64 encoding
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100, facecolor='#1a1a1a', bbox_inches='tight')
        img_buffer.seek(0)
        
        # Generate filename if timestamp provided
        filename = None
        filepath = None
        
        if timestamp and save_to_disk:
            dt = datetime.fromtimestamp(timestamp / 1000)
            filename = f"{symbol}_{timeframe}_{dt.strftime('%Y%m%d_%H%M')}.png"
            filepath = CHARTS_DIR / filename
            
            # Save to disk
            with open(filepath, 'wb') as f:
                f.write(img_buffer.getvalue())
            
            # Store metadata
            indicators = []
            if 'ema_20' in chart_df.columns and chart_df['ema_20'].notna().any():
                indicators.append('EMA_20')
            if 'ema_200' in chart_df.columns and chart_df['ema_200'].notna().any():
                indicators.append('EMA_200')
            if 'vwap' in chart_df.columns and chart_df['vwap'].notna().any():
                indicators.append('VWAP')
            
            store_chart_metadata(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=timestamp,
                filename=filename,
                filepath=str(filepath),
                indicators=indicators
            )
            
            logger.info(f"Chart saved: {filename}")
        
        # Convert to base64
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        plt.close(fig)
        
        return img_base64 if not save_to_disk else str(filepath)
    
    except Exception as e:
        logger.error(f"Failed to generate chart: {e}", exc_info=True)
        return None

def generate_chart_on_candle_complete(
    symbol: str,
    timeframe: str,
    timestamp: int
) -> Optional[str]:
    """
    Generate chart automatically when a candle completes.
    
    Args:
        symbol: Stock symbol
        timeframe: Timeframe ('1min', '5min', 'daily')
        timestamp: Unix timestamp in milliseconds
        
    Returns:
        Filepath to saved chart or None
    """
    try:
        from utils.market_data_db import get_market_data
        
        # Get recent data for chart
        end_time = timestamp
        start_time = timestamp - (24 * 60 * 60 * 1000)  # Last 24 hours
        
        df = get_market_data(symbol, timeframe, start_time, end_time)
        
        if df.empty:
            logger.warning(f"No data available for chart: {symbol} {timeframe}")
            return None
        
        # Generate chart
        filepath = generate_chart_image(
            df=df,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=timestamp,
            save_to_disk=True
        )
        
        return filepath
    
    except Exception as e:
        logger.error(f"Failed to generate chart on candle complete: {e}", exc_info=True)
        return None


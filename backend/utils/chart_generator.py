"""
Chart Generator for Trading Analysis
Generates candlestick charts with OV indicators for AI vision analysis.
"""
import os
import base64
import io
from typing import Dict, Any, Optional
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from utils.logger import setup_logger

logger = setup_logger("chart_generator")

def generate_trading_chart(df: pd.DataFrame, symbol: str, setup_info: Optional[Dict] = None) -> str:
    """
    Generate a candlestick chart with OV indicators for AI vision analysis.
    
    Args:
        df: DataFrame with OHLCV data and indicators
        symbol: Stock symbol
        setup_info: Optional setup information to highlight
        
    Returns:
        Base64-encoded image string
    """
    try:
        if df.empty or len(df) < 50:
            logger.warning(f"Insufficient data for chart: {len(df)} rows")
            return None
        
        # Use last 100 candles for clarity
        chart_df = df.tail(100).copy()
        
        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1])
        fig.patch.set_facecolor('#1a1a1a')
        ax1.set_facecolor('#1a1a1a')
        ax2.set_facecolor('#1a1a1a')
        
        # Prepare data
        dates = pd.to_datetime(chart_df['datetime']) if 'datetime' in chart_df.columns else chart_df.index
        opens = chart_df['open'].values
        highs = chart_df['high'].values
        lows = chart_df['low'].values
        closes = chart_df['close'].values
        volumes = chart_df['volume'].values if 'volume' in chart_df.columns else None
        
        # Plot candlesticks
        for i in range(len(chart_df)):
            color = '#10b981' if closes[i] >= opens[i] else '#ef4444'  # Green for up, red for down
            body_bottom = min(opens[i], closes[i])
            body_top = max(opens[i], closes[i])
            body_height = abs(closes[i] - opens[i])
            
            # Draw wick
            ax1.plot([i, i], [lows[i], highs[i]], color=color, linewidth=1, alpha=0.8)
            # Draw body
            rect = Rectangle((i - 0.3, body_bottom), 0.6, body_height, 
                           facecolor=color, edgecolor=color, alpha=0.8)
            ax1.add_patch(rect)
        
        # Plot SMAs
        if 'sma_8' in chart_df.columns:
            ax1.plot(range(len(chart_df)), chart_df['sma_8'].values, 
                    color='#3b82f6', linewidth=1.5, label='SMA 8', alpha=0.8)
        if 'sma_20' in chart_df.columns:
            ax1.plot(range(len(chart_df)), chart_df['sma_20'].values, 
                    color='#f59e0b', linewidth=1.5, label='SMA 20', alpha=0.8)
        if 'sma_200' in chart_df.columns:
            ax1.plot(range(len(chart_df)), chart_df['sma_200'].values, 
                    color='#8b5cf6', linewidth=2, label='SMA 200', alpha=0.8)
        
        # Highlight current price
        latest_idx = len(chart_df) - 1
        latest_price = closes[latest_idx]
        ax1.axhline(y=latest_price, color='#ffffff', linestyle='--', linewidth=1, alpha=0.5, label='Current Price')
        
        # Highlight setup if provided
        if setup_info:
            setup_type = setup_info.get('type', '')
            entry_price = setup_info.get('entry_price', latest_price)
            stop_loss = setup_info.get('stop_loss')
            take_profit = setup_info.get('take_profit')
            
            # Mark entry
            ax1.plot(latest_idx, entry_price, marker='o', markersize=10, 
                    color='#10b981', label=f'Entry ({setup_type})', zorder=5)
            
            # Mark stop loss
            if stop_loss:
                ax1.axhline(y=stop_loss, color='#ef4444', linestyle=':', linewidth=2, 
                           label='Stop Loss', alpha=0.7)
            
            # Mark take profit
            if take_profit:
                ax1.axhline(y=take_profit, color='#10b981', linestyle=':', linewidth=2, 
                           label='Take Profit', alpha=0.7)
        
        # Format price chart
        ax1.set_ylabel('Price ($)', color='#e5e7eb', fontsize=10)
        ax1.set_title(f'{symbol} - Oliver Vélez Analysis Chart', color='#e5e7eb', fontsize=14, fontweight='bold')
        ax1.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='#374151', labelcolor='#e5e7eb', fontsize=8)
        ax1.grid(True, alpha=0.2, color='#374151')
        ax1.tick_params(colors='#9ca3af')
        ax1.set_xticks([])  # Remove x-axis labels on price chart
        
        # Plot volume
        if volumes is not None:
            volume_colors = ['#10b981' if closes[i] >= opens[i] else '#ef4444' for i in range(len(chart_df))]
            ax2.bar(range(len(chart_df)), volumes, color=volume_colors, alpha=0.6, width=0.8)
            
            # Plot volume average if available
            if 'volume_ma' in chart_df.columns:
                ax2.plot(range(len(chart_df)), chart_df['volume_ma'].values, 
                        color='#f59e0b', linewidth=1.5, label='Volume MA', alpha=0.8)
                ax2.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='#374151', labelcolor='#e5e7eb', fontsize=8)
        
        ax2.set_ylabel('Volume', color='#e5e7eb', fontsize=10)
        ax2.set_xlabel('Time', color='#e5e7eb', fontsize=10)
        ax2.grid(True, alpha=0.2, color='#374151')
        ax2.tick_params(colors='#9ca3af')
        
        # Format x-axis with dates
        if len(chart_df) > 0:
            step = max(1, len(chart_df) // 10)
            ax2.set_xticks(range(0, len(chart_df), step))
            if 'datetime' in chart_df.columns:
                date_labels = [pd.to_datetime(d).strftime('%H:%M') for d in chart_df['datetime'].iloc[::step]]
            else:
                date_labels = [str(i) for i in range(0, len(chart_df), step)]
            ax2.set_xticklabels(date_labels, rotation=45, ha='right')
        
        plt.tight_layout()
        
        # Convert to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor='#1a1a1a', dpi=100, bbox_inches='tight')
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        
        logger.info(f"Chart generated for {symbol}: {len(image_base64)} bytes")
        return image_base64
        
    except Exception as e:
        logger.error(f"Failed to generate chart for {symbol}: {e}", exc_info=True)
        return None


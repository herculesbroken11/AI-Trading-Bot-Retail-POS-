"""
Chart Generator for AI Vision Analysis
Creates visual charts showing price action, indicators, and OV trading setups.
"""
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
import numpy as np
from io import BytesIO
import base64
from typing import Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger("chart_generator")

def generate_trading_chart(
    df: pd.DataFrame,
    symbol: str,
    setup: Dict[str, Any],
    market_summary: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Generate a trading chart image for AI vision analysis.
    
    Args:
        df: DataFrame with OHLCV data and indicators
        symbol: Stock symbol
        setup: OV setup dictionary
        market_summary: Market summary data
        
    Returns:
        Base64 encoded image string or None
    """
    try:
        if df.empty or len(df) < 50:
            logger.warning(f"Insufficient data for chart: {len(df)} candles")
            return None
        
        # Use last 100 candles for clarity
        chart_df = df.tail(100).copy()
        
        # Ensure datetime column exists and is properly formatted
        if 'datetime' not in chart_df.columns:
            if 'timestamp' in chart_df.columns:
                chart_df['datetime'] = pd.to_datetime(chart_df['timestamp'])
            elif chart_df.index.name == 'datetime' or isinstance(chart_df.index, pd.DatetimeIndex):
                chart_df['datetime'] = chart_df.index
            else:
                # Create datetime from index if it's numeric (assuming it's sequential)
                chart_df['datetime'] = pd.date_range(end=pd.Timestamp.now(), periods=len(chart_df), freq='1min')
        else:
            # Ensure datetime is datetime type
            chart_df['datetime'] = pd.to_datetime(chart_df['datetime'])
        
        # Create figure with subplots
        fig = plt.figure(figsize=(14, 10), facecolor='#1a1a1a')
        gs = fig.add_gridspec(4, 1, height_ratios=[3, 1, 1, 1], hspace=0.3)
        
        # Main price chart
        ax1 = fig.add_subplot(gs[0])
        ax1.set_facecolor('#0f0f0f')
        
        # Plot candlesticks
        for idx, row in chart_df.iterrows():
            color = '#10b981' if row['close'] >= row['open'] else '#ef4444'
            body_height = abs(row['close'] - row['open'])
            wick_top = max(row['close'], row['open'])
            wick_bottom = min(row['close'], row['open'])
            
            # Candle body
            rect = Rectangle(
                (mdates.date2num(row['datetime']) - 0.2, min(row['close'], row['open'])),
                0.4,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.5
            )
            ax1.add_patch(rect)
            
            # Wicks
            ax1.plot(
                [mdates.date2num(row['datetime']), mdates.date2num(row['datetime'])],
                [row['low'], wick_bottom],
                color=color,
                linewidth=0.8
            )
            ax1.plot(
                [mdates.date2num(row['datetime']), mdates.date2num(row['datetime'])],
                [wick_top, row['high']],
                color=color,
                linewidth=0.8
            )
        
        # Plot SMAs
        if 'sma_8' in chart_df.columns:
            ax1.plot(
                chart_df['datetime'],
                chart_df['sma_8'],
                color='#3b82f6',
                linewidth=1.5,
                label='SMA8',
                alpha=0.8
            )
        if 'sma_20' in chart_df.columns:
            ax1.plot(
                chart_df['datetime'],
                chart_df['sma_20'],
                color='#f59e0b',
                linewidth=1.5,
                label='SMA20',
                alpha=0.8
            )
        if 'sma_200' in chart_df.columns:
            ax1.plot(
                chart_df['datetime'],
                chart_df['sma_200'],
                color='#8b5cf6',
                linewidth=2,
                label='SMA200',
                alpha=0.9
            )
        
        # Mark entry, stop, and target if available
        latest = chart_df.iloc[-1]
        if setup.get('entry_price'):
            entry_price = float(setup['entry_price'])
            ax1.axhline(y=entry_price, color='#10b981', linestyle='--', linewidth=2, label='Entry', alpha=0.7)
            ax1.scatter(
                mdates.date2num(latest['datetime']),
                entry_price,
                color='#10b981',
                s=100,
                marker='^',
                zorder=5,
                edgecolors='white',
                linewidths=1
            )
        
        if setup.get('stop_loss'):
            stop_price = float(setup['stop_loss'])
            ax1.axhline(y=stop_price, color='#ef4444', linestyle='--', linewidth=2, label='Stop Loss', alpha=0.7)
        
        if setup.get('take_profit'):
            target_price = float(setup['take_profit'])
            ax1.axhline(y=target_price, color='#3b82f6', linestyle='--', linewidth=2, label='Take Profit', alpha=0.7)
        
        # Highlight setup area
        if len(chart_df) > 10:
            setup_start = len(chart_df) - 20
            setup_end = len(chart_df)
            ax1.axvspan(
                mdates.date2num(chart_df.iloc[setup_start]['datetime']),
                mdates.date2num(chart_df.iloc[-1]['datetime']),
                alpha=0.1,
                color='#667eea',
                label='Setup Zone'
            )
        
        ax1.set_title(
            f'{symbol} - {setup.get("type", "Setup")} | OV Trading Analysis',
            color='white',
            fontsize=14,
            fontweight='bold',
            pad=10
        )
        ax1.set_ylabel('Price ($)', color='white', fontsize=11)
        ax1.tick_params(colors='white', labelsize=9)
        ax1.grid(True, alpha=0.2, color='gray')
        ax1.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='gray', labelcolor='white', fontsize=8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        
        # Volume chart
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        ax2.set_facecolor('#0f0f0f')
        if 'volume' in chart_df.columns:
            colors = ['#10b981' if chart_df.iloc[i]['close'] >= chart_df.iloc[i]['open'] else '#ef4444' 
                     for i in range(len(chart_df))]
            ax2.bar(
                chart_df['datetime'],
                chart_df['volume'],
                color=colors,
                alpha=0.6,
                width=0.8
            )
            if 'volume_ma' in chart_df.columns:
                ax2.plot(
                    chart_df['datetime'],
                    chart_df['volume_ma'],
                    color='#f59e0b',
                    linewidth=1.5,
                    label='Volume MA',
                    alpha=0.8
                )
        ax2.set_ylabel('Volume', color='white', fontsize=10)
        ax2.tick_params(colors='white', labelsize=8)
        ax2.grid(True, alpha=0.2, color='gray')
        ax2.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='gray', labelcolor='white', fontsize=7)
        
        # RSI chart
        ax3 = fig.add_subplot(gs[2], sharex=ax1)
        ax3.set_facecolor('#0f0f0f')
        if 'rsi_14' in chart_df.columns:
            ax3.plot(
                chart_df['datetime'],
                chart_df['rsi_14'],
                color='#8b5cf6',
                linewidth=1.5,
                label='RSI(14)'
            )
            ax3.axhline(y=70, color='#ef4444', linestyle='--', alpha=0.5, label='Overbought')
            ax3.axhline(y=30, color='#10b981', linestyle='--', alpha=0.5, label='Oversold')
            ax3.fill_between(
                chart_df['datetime'],
                30,
                70,
                alpha=0.1,
                color='#3b82f6',
                label='RSI Range'
            )
        ax3.set_ylabel('RSI', color='white', fontsize=10)
        ax3.set_ylim(0, 100)
        ax3.tick_params(colors='white', labelsize=8)
        ax3.grid(True, alpha=0.2, color='gray')
        ax3.legend(loc='upper left', facecolor='#1a1a1a', edgecolor='gray', labelcolor='white', fontsize=7)
        
        # 4 Fantastics Status
        ax4 = fig.add_subplot(gs[3])
        ax4.set_facecolor('#0f0f0f')
        ax4.axis('off')
        
        fantastics = setup.get('fantastics', {})
        fantastic_names = [
            'Price > SMA200',
            'SMA Alignment',
            'Volume > Avg',
            'RSI in Range'
        ]
        fantastic_status = [
            fantastics.get('price_above_sma200', False),
            fantastics.get('sma_aligned', False),
            fantastics.get('volume_above_average', False),
            fantastics.get('rsi_in_range', False)
        ]
        
        # Create status indicators
        y_pos = 0.7
        for i, (name, status) in enumerate(zip(fantastic_names, fantastic_status)):
            color = '#10b981' if status else '#ef4444'
            symbol_char = '✓' if status else '✗'
            ax4.text(
                0.1 + i * 0.22,
                y_pos,
                f'{symbol_char} {name}',
                color=color,
                fontsize=10,
                fontweight='bold',
                ha='center',
                transform=ax4.transAxes
            )
        
        # Setup info
        setup_type = setup.get('type', 'Unknown')
        setup_direction = setup.get('direction', 'N/A')
        confidence = setup.get('confidence', 0)
        
        info_text = f"Setup: {setup_type} | Direction: {setup_direction} | Confidence: {confidence:.1%}"
        ax4.text(
            0.5,
            0.3,
            info_text,
            color='white',
            fontsize=11,
            fontweight='bold',
            ha='center',
            transform=ax4.transAxes
        )
        
        # Market summary info
        if market_summary:
            current_price = market_summary.get('current_price', latest.get('close', 0))
            atr = market_summary.get('atr_14', latest.get('atr_14', 0))
            info_text2 = f"Price: ${current_price:.2f} | ATR(14): ${atr:.2f}"
            ax4.text(
                0.5,
                0.1,
                info_text2,
                color='#9ca3af',
                fontsize=9,
                ha='center',
                transform=ax4.transAxes
            )
        
        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Save to bytes
        buf = BytesIO()
        plt.savefig(
            buf,
            format='png',
            dpi=100,
            facecolor='#1a1a1a',
            edgecolor='none',
            bbox_inches='tight'
        )
        buf.seek(0)
        
        # Convert to base64
        image_base64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        plt.close(fig)
        
        logger.info(f"Chart generated successfully for {symbol}")
        return image_base64
        
    except Exception as e:
        logger.error(f"Failed to generate chart for {symbol}: {e}", exc_info=True)
        return None


"""
Risk management and position sizing utilities.
"""
import os
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# Risk parameters from environment
MAX_TRADE_AMOUNT = float(os.getenv("MAX_TRADE_AMOUNT", "300"))
MAX_POSITION_SIZE = int(os.getenv("MAX_POSITION_SIZE", "1"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.0"))
TAKE_PROFIT_PERCENT = float(os.getenv("TAKE_PROFIT_PERCENT", "3.0"))

def calculate_position_size(
    account_value: float,
    entry_price: float,
    stop_loss_price: float,
    max_risk_per_trade: float = MAX_TRADE_AMOUNT
) -> int:
    """
    Calculate position size based on risk management rules.
    
    Args:
        account_value: Total account value
        entry_price: Entry price for the trade
        stop_loss_price: Stop loss price
        max_risk_per_trade: Maximum dollar amount to risk per trade
        
    Returns:
        Number of shares to trade
    """
    if entry_price <= 0 or stop_loss_price <= 0:
        return 0
    
    risk_per_share = abs(entry_price - stop_loss_price)
    if risk_per_share == 0:
        return 0
    
    # Calculate shares based on max risk
    shares = int(max_risk_per_trade / risk_per_share)
    
    # Ensure we don't exceed max position size
    shares = min(shares, MAX_POSITION_SIZE * 100)  # Assuming 100 shares per unit
    
    return max(1, shares)  # At least 1 share

def validate_trade_signal(signal: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate a trading signal before execution.
    
    Args:
        signal: Trading signal dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["action", "entry", "stop", "target", "symbol"]
    
    for field in required_fields:
        if field not in signal:
            return False, f"Missing required field: {field}"
    
    if signal["action"] not in ["BUY", "SELL", "SHORT"]:
        return False, f"Invalid action: {signal['action']}"
    
    entry = float(signal["entry"])
    stop = float(signal["stop"])
    target = float(signal["target"])
    
    if entry <= 0 or stop <= 0 or target <= 0:
        return False, "Prices must be positive"
    
    # Validate stop loss is reasonable (within 5% of entry)
    stop_loss_pct = abs(entry - stop) / entry * 100
    if stop_loss_pct > 5.0:
        return False, f"Stop loss too wide: {stop_loss_pct:.2f}%"
    
    # Validate take profit is reasonable
    take_profit_pct = abs(target - entry) / entry * 100
    if take_profit_pct > 10.0:
        return False, f"Take profit too wide: {take_profit_pct:.2f}%"
    
    return True, None

def calculate_stop_loss(entry_price: float, is_long: bool = True) -> float:
    """
    Calculate stop loss price based on percentage.
    
    Args:
        entry_price: Entry price
        is_long: True for long positions, False for short
        
    Returns:
        Stop loss price
    """
    if is_long:
        return entry_price * (1 - STOP_LOSS_PERCENT / 100)
    else:
        return entry_price * (1 + STOP_LOSS_PERCENT / 100)

def calculate_take_profit(entry_price: float, is_long: bool = True) -> float:
    """
    Calculate take profit price based on percentage.
    
    Args:
        entry_price: Entry price
        is_long: True for long positions, False for short
        
    Returns:
        Take profit price
    """
    if is_long:
        return entry_price * (1 + TAKE_PROFIT_PERCENT / 100)
    else:
        return entry_price * (1 - TAKE_PROFIT_PERCENT / 100)


"""
Position Management Module
Handles automated position management: trailing stops, break-even, auto-close, additions.
"""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger
from utils.helpers import get_valid_access_token, schwab_api_request
from api.orders import SCHWAB_ACCOUNTS_URL

logger = setup_logger("position_manager")

class PositionManager:
    """
    Manages open positions with automated features:
    - Trailing stops
    - Break-even stops
    - Auto-close at 4:00 PM ET
    - Position scaling (additions)
    """
    
    def __init__(self, performance_analyzer=None):
        self.positions_file = "data/active_positions.json"
        self.max_risk_per_trade = float(os.getenv("MAX_RISK_PER_TRADE", "300"))
        self.auto_close_time = "16:00"  # 4:00 PM ET
        self.performance_analyzer = performance_analyzer
        
        # Load optimized parameters if available
        if performance_analyzer:
            params = performance_analyzer.get_optimized_parameters()
            self.trailing_stop_percent = params.get("trailing_stop_atr", 0.5)
            self.breakeven_profit_atr = params.get("breakeven_atr", 1.0)
            self.stop_distance_atr = params.get("stop_distance_atr", 1.5)
            self.target_distance_atr = params.get("target_distance_atr", 3.0)
        else:
        self.trailing_stop_percent = 0.5  # Trail by 0.5 ATR
        self.breakeven_profit_atr = 1.0  # Move to BE after 1 ATR profit
            self.stop_distance_atr = 1.5
            self.target_distance_atr = 3.0
        
    def load_active_positions(self) -> List[Dict[str, Any]]:
        """Load active positions from file."""
        if not os.path.exists(self.positions_file):
            return []
        
        try:
            with open(self.positions_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load positions: {e}")
            return []
    
    def save_active_positions(self, positions: List[Dict[str, Any]]):
        """Save active positions to file."""
        os.makedirs("data", exist_ok=True)
        try:
            with open(self.positions_file, 'w') as f:
                json.dump(positions, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")
    
    def add_position(self, position: Dict[str, Any]):
        """Add a new position to tracking."""
        positions = self.load_active_positions()
        
        # Check if position already exists
        existing = next(
            (p for p in positions if p.get('symbol') == position.get('symbol') and 
             p.get('account_id') == position.get('account_id')), 
            None
        )
        
        if existing:
            logger.warning(f"Position for {position.get('symbol')} already exists")
            return
        
        position['entry_time'] = datetime.now(timezone.utc).isoformat()
        position['initial_stop'] = position.get('stop_loss')
        position['highest_price'] = position.get('entry_price')  # For longs
        position['lowest_price'] = position.get('entry_price')   # For shorts
        position['breakeven_set'] = False
        position['additions'] = []
        
        positions.append(position)
        self.save_active_positions(positions)
        logger.info(f"Added position: {position.get('symbol')} @ {position.get('entry_price')}")
    
    def update_position(self, symbol: str, account_id: str, updates: Dict[str, Any]):
        """Update position with new data."""
        positions = self.load_active_positions()
        
        for pos in positions:
            if pos.get('symbol') == symbol and pos.get('account_id') == account_id:
                pos.update(updates)
                self.save_active_positions(positions)
                logger.info(f"Updated position: {symbol}")
                return True
        
        return False
    
    def remove_position(self, symbol: str, account_id: str):
        """Remove position from tracking."""
        positions = self.load_active_positions()
        positions = [p for p in positions if not (
            p.get('symbol') == symbol and p.get('account_id') == account_id
        )]
        self.save_active_positions(positions)
        logger.info(f"Removed position: {symbol}")
    
    def update_trailing_stop(self, position: Dict[str, Any], current_price: float) -> Optional[float]:
        """
        Update trailing stop based on current price.
        
        Args:
            position: Position dictionary
            current_price: Current market price
            
        Returns:
            New stop price if updated, None otherwise
        """
        direction = position.get('direction', 'LONG')
        entry_price = position.get('entry_price')
        initial_stop = position.get('initial_stop')
        atr = position.get('atr', 0)
        
        if not entry_price or not initial_stop or not atr:
            return None
        
        if direction == 'LONG':
            # Update highest price
            if current_price > position.get('highest_price', entry_price):
                position['highest_price'] = current_price
                
                # Calculate trailing stop
                trailing_stop = current_price - (atr * self.trailing_stop_percent)
                
                # Only move stop up, never down
                current_stop = position.get('current_stop', initial_stop)
                if trailing_stop > current_stop:
                    position['current_stop'] = trailing_stop
                    return trailing_stop
        
        elif direction == 'SHORT':
            # Update lowest price
            if current_price < position.get('lowest_price', entry_price):
                position['lowest_price'] = current_price
                
                # Calculate trailing stop
                trailing_stop = current_price + (atr * self.trailing_stop_percent)
                
                # Only move stop down, never up
                current_stop = position.get('current_stop', initial_stop)
                if trailing_stop < current_stop:
                    position['current_stop'] = trailing_stop
                    return trailing_stop
        
        return None
    
    def check_breakeven(self, position: Dict[str, Any], current_price: float) -> bool:
        """
        Check if position should move to break-even.
        
        Args:
            position: Position dictionary
            current_price: Current market price
            
        Returns:
            True if break-even should be set
        """
        if position.get('breakeven_set'):
            return False
        
        direction = position.get('direction', 'LONG')
        entry_price = position.get('entry_price')
        atr = position.get('atr', 0)
        
        if not entry_price or not atr:
            return False
        
        if direction == 'LONG':
            profit = current_price - entry_price
            if profit >= (atr * self.breakeven_profit_atr):
                # Move stop to entry (break-even)
                position['current_stop'] = entry_price
                position['breakeven_set'] = True
                return True
        
        elif direction == 'SHORT':
            profit = entry_price - current_price
            if profit >= (atr * self.breakeven_profit_atr):
                # Move stop to entry (break-even)
                position['current_stop'] = entry_price
                position['breakeven_set'] = True
                return True
        
        return False
    
    def can_add_to_position(self, position: Dict[str, Any], current_price: float) -> bool:
        """
        Check if position can be scaled (added to).
        
        Args:
            position: Position dictionary
            current_price: Current market price
            
        Returns:
            True if addition is allowed
        """
        direction = position.get('direction', 'LONG')
        entry_price = position.get('entry_price')
        atr = position.get('atr', 0)
        max_additions = 2  # Maximum 2 additions
        
        if len(position.get('additions', [])) >= max_additions:
            return False
        
        if direction == 'LONG':
            # Can add if price moved in favor by 1 ATR
            profit = current_price - entry_price
            if profit >= (atr * 1.0):
                return True
        
        elif direction == 'SHORT':
            # Can add if price moved in favor by 1 ATR
            profit = entry_price - current_price
            if profit >= (atr * 1.0):
                return True
        
        return False
    
    def add_to_position(self, position: Dict[str, Any], additional_shares: int, price: float):
        """Record addition to position."""
        if 'additions' not in position:
            position['additions'] = []
        
        position['additions'].append({
            'shares': additional_shares,
            'price': price,
            'time': datetime.now(timezone.utc).isoformat()
        })
        
        # Update average entry price
        total_shares = position.get('quantity', 0) + sum(a['shares'] for a in position['additions'])
        total_cost = (position.get('quantity', 0) * position.get('entry_price', 0)) + \
                     sum(a['shares'] * a['price'] for a in position['additions'])
        
        if total_shares > 0:
            position['average_entry'] = total_cost / total_shares
        
        logger.info(f"Added {additional_shares} shares to {position.get('symbol')} @ {price}")
    
    def should_auto_close(self) -> bool:
        """
        Check if it's time to auto-close positions (4:00 PM ET).
        
        Returns:
            True if positions should be closed
        """
        # Get current time in ET
        now_utc = datetime.now(timezone.utc)
        # ET is UTC-5 (EST) or UTC-4 (EDT) - using UTC-5 for simplicity
        et_offset = -5
        now_et = now_utc.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=et_offset)))
        
        current_time = now_et.strftime("%H:%M")
        return current_time >= self.auto_close_time
    
    def close_all_positions(self) -> List[Dict[str, Any]]:
        """
        Close all open positions.
        
        Returns:
            List of closed positions
        """
        positions = self.load_active_positions()
        if not positions:
            return []
        
        # Get valid access token (automatically refreshed if needed)
        access_token = get_valid_access_token()
        if not access_token:
            logger.error("Not authenticated - cannot close positions")
            return []
        
        closed = []
        
        for position in positions:
            try:
                symbol = position.get('symbol')
                account_id = position.get('account_id')
                quantity = position.get('quantity', 0)
                direction = position.get('direction', 'LONG')
                
                if not symbol or not account_id or quantity == 0:
                    continue
                
                # Determine order side (opposite of position)
                order_side = "SELL" if direction == "LONG" else "BUY"
                
                # Place market order to close
                order = {
                    "orderType": "MARKET",
                    "session": "NORMAL",
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [{
                        "instruction": order_side,
                        "quantity": quantity,
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }]
                }
                
                # Use account hash for API call
                from api.orders import get_validated_account_hash
                account_hash, _ = get_validated_account_hash(account_id, access_token)
                url = f"{SCHWAB_ACCOUNTS_URL}/{account_hash}/orders"
                response = schwab_api_request("POST", url, access_token, data=order)
                
                if response.status_code == 201:
                    # Try to get current price for accurate P&L
                    exit_price = position.get('current_price') or position.get('entry_price', 0)
                    try:
                        from api.quotes import SCHWAB_QUOTES_URL
                        quote_url = f"{SCHWAB_QUOTES_URL}?symbols={symbol}"
                        quote_response = schwab_api_request("GET", quote_url, access_token)
                        quote = quote_response.json()
                        if isinstance(quote, dict) and symbol in quote:
                            quote_data = quote[symbol]
                            exit_price = quote_data.get('lastPrice') or quote_data.get('mark', exit_price)
                    except:
                        pass  # Use fallback price
                    
                    # Calculate P&L
                    entry_price = position.get('entry_price') or position.get('average_entry', 0)
                    direction = position.get('direction', 'LONG')
                    if direction == 'LONG':
                        pnl = (exit_price - entry_price) * quantity
                    else:
                        pnl = (entry_price - exit_price) * quantity
                    
                    # Record trade outcome if performance analyzer is available
                    if self.performance_analyzer:
                        try:
                            trade_data = {
                                "symbol": symbol,
                                "setup_type": position.get("setup_type", "unknown"),
                                "entry_price": entry_price,
                                "exit_price": exit_price,
                                "quantity": quantity,
                                "direction": direction,
                                "pnl": pnl,
                                "status": "CLOSED",
                                "entry_time": position.get("entry_time"),
                                "exit_time": datetime.now(timezone.utc).isoformat()
                            }
                            self.performance_analyzer.record_trade_outcome(trade_data)
                        except Exception as e:
                            logger.error(f"Failed to record trade outcome: {e}")
                    
                    logger.info(f"Closed position: {symbol} ({quantity} shares) - P&L: ${pnl:.2f}")
                    closed.append(position)
                    self.remove_position(symbol, account_id)
                else:
                    logger.error(f"Failed to close {symbol}: {response.text}")
            
            except Exception as e:
                logger.error(f"Error closing position {position.get('symbol')}: {e}")
        
        return closed
    
    def update_all_positions(self, price_data: Dict[str, float]):
        """
        Update all positions with current prices and manage stops.
        
        Args:
            price_data: Dictionary mapping symbol to current price
        """
        positions = self.load_active_positions()
        updated = False
        
        for position in positions:
            symbol = position.get('symbol')
            if symbol not in price_data:
                continue
            
            current_price = price_data[symbol]
            
            # Update trailing stop
            new_stop = self.update_trailing_stop(position, current_price)
            if new_stop:
                # Update stop order on broker
                self._update_stop_order(position, new_stop)
                updated = True
            
            # Check break-even
            if self.check_breakeven(position, current_price):
                # Update stop order to break-even
                self._update_stop_order(position, position['current_stop'])
                updated = True
            
            # Check if can add to position
            if self.can_add_to_position(position, current_price):
                # Signal for addition (manual or automated)
                logger.info(f"Position {symbol} eligible for addition at {current_price}")
        
        if updated:
            self.save_active_positions(positions)
    
    def _update_stop_order(self, position: Dict[str, Any], new_stop: float):
        """Update stop order on broker."""
        # This would update the stop order via Schwab API
        # For now, just log
        logger.info(f"Updating stop for {position.get('symbol')} to {new_stop}")
        # TODO: Implement actual order update via Schwab API


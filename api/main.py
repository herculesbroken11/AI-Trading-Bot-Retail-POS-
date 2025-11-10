"""
FastAPI application for Schwab AI Trading Bot
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import json

from core.config import Config
from core.strategy_stub import TradingStrategy

# Initialize FastAPI app
app = FastAPI(
    title="Schwab AI Trading Bot API",
    description="AI-assisted trading engine with Charles Schwab integration",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize strategy
strategy = TradingStrategy()

# Pydantic models
class TradingSignal(BaseModel):
    """Trading signal model"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float
    entry_price: float
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    reasoning: Optional[str] = None

class SimulateRequest(BaseModel):
    """Simulate trade request"""
    symbol: str
    action: str
    quantity: int = 1
    price: Optional[float] = None

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Schwab AI Trading Bot API",
        "version": "1.0.0",
        "simulation_mode": Config.SIMULATION_MODE,
        "live_trading_enabled": Config.ENABLE_LIVE_TRADING,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "simulation_mode": Config.SIMULATION_MODE
    }

@app.post("/simulate")
async def simulate_trade(request: SimulateRequest) -> Dict[str, Any]:
    """
    Simulate a trade execution (no actual order placed)
    
    Args:
        request: Simulate trade request
        
    Returns:
        Simulated trade result
    """
    try:
        # Create signal
        signal = {
            "symbol": request.symbol,
            "action": request.action,
            "confidence": 0.8,
            "entry_price": request.price or 100.0,
            "stop_loss": request.price * 0.98 if request.price else 98.0,
            "target_price": request.price * 1.02 if request.price else 102.0,
            "timestamp": datetime.now().isoformat()
        }
        
        # Simulate trade
        result = strategy.simulate_trade(signal)
        result["quantity"] = request.quantity
        
        return {
            "status": "success",
            "simulated": True,
            "trade": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/signal")
async def process_signal(signal: TradingSignal) -> Dict[str, Any]:
    """
    Process a trading signal (store and log, no execution unless enabled)
    
    Args:
        signal: Trading signal
        
    Returns:
        Processing result
    """
    try:
        # Validate signal
        signal_dict = signal.dict()
        if not strategy.validate_signal(signal_dict):
            raise HTTPException(status_code=400, detail="Invalid signal format")
        
        # Log signal
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "signal": signal_dict,
            "processed": True,
            "executed": False
        }
        
        # Only execute if live trading is explicitly enabled
        if Config.ENABLE_LIVE_TRADING and not Config.SIMULATION_MODE:
            # TODO: Implement actual trade execution
            log_entry["executed"] = False
            log_entry["reason"] = "Live trading not yet implemented"
        else:
            log_entry["reason"] = "Simulation mode - signal logged but not executed"
        
        # TODO: Store in database
        # For now, just return the result
        
        return {
            "status": "success",
            "signal_received": True,
            "signal": signal_dict,
            "executed": log_entry["executed"],
            "reason": log_entry["reason"],
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/config")
async def get_config() -> Dict[str, Any]:
    """
    Get current configuration (safe values only)
    
    Returns:
        Configuration dictionary
    """
    return {
        "simulation_mode": Config.SIMULATION_MODE,
        "live_trading_enabled": Config.ENABLE_LIVE_TRADING,
        "max_loss_per_trade": Config.MAX_LOSS_PER_TRADE,
        "max_position_size": Config.MAX_POSITION_SIZE,
        "risk_percentage": Config.RISK_PERCENTAGE,
        "api_host": Config.API_HOST,
        "api_port": Config.API_PORT,
        "debug": Config.DEBUG
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=Config.API_HOST,
        port=Config.API_PORT,
        reload=Config.DEBUG
    )

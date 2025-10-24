"""
FastAPI main application for AI Trading Bot
Handles AI ↔ VPS communication and trading operations
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import uvicorn
from datetime import datetime
import json

from core.config import config
from core.logger import logger
from core.schwab_api import SchwabAPI
from core.velez_strategy import VelezStrategy, TradingSignal
from core.ai_analyzer import AIAnalyzer
from core.trade_executor import TradeExecutor

app = FastAPI(
    title="AI Trading Bot API",
    description="AI-assisted trading engine with Oliver Vélez strategies",
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

# Global instances
velez_strategy = VelezStrategy()
trade_executor = TradeExecutor()

# Pydantic models
class MarketDataRequest(BaseModel):
    symbols: List[str]
    period_type: str = "day"
    period: int = 1
    frequency_type: str = "minute"
    frequency: int = 1

class SignalAnalysisRequest(BaseModel):
    symbol: str
    signal_type: str
    entry_price: float
    stop_loss: float
    target_price: float
    confidence: float
    setup_quality: str

class TradeExecutionRequest(BaseModel):
    symbol: str
    instruction: str  # BUY, SELL, BUY_TO_COVER, SELL_SHORT
    quantity: int
    order_type: str = "MARKET"  # MARKET, LIMIT
    price: Optional[float] = None

class AIAnalysisResponse(BaseModel):
    validation_result: str
    confidence_score: float
    recommendation: str
    reasoning: str
    risk_assessment: str
    market_context: str
    strengths: List[str]
    weaknesses: List[str]
    alternative_actions: List[str]
    timestamp: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "config_valid": config.validate_config()
    }

@app.post("/market-data")
async def get_market_data(request: MarketDataRequest):
    """Get market data for specified symbols"""
    try:
        async with SchwabAPI() as schwab_api:
            market_data = {}
            
            for symbol in request.symbols:
                data = await schwab_api.get_market_data(
                    symbol=symbol,
                    period_type=request.period_type,
                    period=request.period,
                    frequency_type=request.frequency_type,
                    frequency=request.frequency
                )
                
                if data is not None:
                    market_data[symbol] = data.to_dict('records')
                else:
                    logger.warning(f"Failed to get market data for {symbol}")
            
            return {
                "status": "success",
                "data": market_data,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting market data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-signals")
async def analyze_signals(request: MarketDataRequest):
    """Analyze trading signals for specified symbols"""
    try:
        async with SchwabAPI() as schwab_api:
            async with AIAnalyzer() as ai_analyzer:
                all_signals = []
                market_data_dict = {}
                
                # Get market data for all symbols
                for symbol in request.symbols:
                    data = await schwab_api.get_market_data(
                        symbol=symbol,
                        period_type=request.period_type,
                        period=request.period,
                        frequency_type=request.frequency_type,
                        frequency=request.frequency
                    )
                    
                    if data is not None:
                        market_data_dict[symbol] = data
                        
                        # Analyze patterns
                        signals = velez_strategy.analyze_all_patterns(data, symbol)
                        
                        # Validate signals
                        valid_signals = [s for s in signals if velez_strategy.validate_signal(s, data)]
                        all_signals.extend(valid_signals)
                
                # AI analysis of all signals
                if all_signals:
                    ai_results = await ai_analyzer.batch_analyze_signals(all_signals, market_data_dict)
                    
                    return {
                        "status": "success",
                        "signals_found": len(all_signals),
                        "ai_analysis": ai_results,
                        "market_summary": ai_analyzer.create_market_summary(ai_results),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    return {
                        "status": "success",
                        "signals_found": 0,
                        "message": "No valid trading signals found",
                        "timestamp": datetime.now().isoformat()
                    }
                    
    except Exception as e:
        logger.error(f"Error analyzing signals: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate-signal")
async def validate_signal(request: SignalAnalysisRequest):
    """Validate a specific trading signal using AI"""
    try:
        async with AIAnalyzer() as ai_analyzer:
            async with SchwabAPI() as schwab_api:
                # Get market data for the symbol
                market_data = await schwab_api.get_market_data(request.symbol)
                
                if market_data is None:
                    raise HTTPException(status_code=404, detail=f"No market data found for {request.symbol}")
                
                # Create signal object
                signal = TradingSignal(
                    signal_type=request.signal_type,
                    symbol=request.symbol,
                    entry_price=request.entry_price,
                    stop_loss=request.stop_loss,
                    target_price=request.target_price,
                    confidence=request.confidence,
                    timestamp=datetime.now(),
                    setup_quality=request.setup_quality,
                    risk_reward_ratio=(request.target_price - request.entry_price) / (request.entry_price - request.stop_loss)
                )
                
                # AI analysis
                analysis = await ai_analyzer.analyze_signal(signal, market_data)
                
                return {
                    "status": "success",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat()
                }
                
    except Exception as e:
        logger.error(f"Error validating signal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute-trade")
async def execute_trade(request: TradeExecutionRequest, background_tasks: BackgroundTasks):
    """Execute a trade order"""
    try:
        # Validate trade parameters
        if request.quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        
        if request.order_type == "LIMIT" and request.price is None:
            raise HTTPException(status_code=400, detail="Price required for limit orders")
        
        # Execute trade
        result = await trade_executor.execute_trade(
            symbol=request.symbol,
            instruction=request.instruction,
            quantity=request.quantity,
            order_type=request.order_type,
            price=request.price
        )
        
        if result:
            # Log trade execution
            background_tasks.add_task(
                trade_executor.log_trade_execution,
                request.symbol,
                request.instruction,
                request.quantity,
                result
            )
            
            return {
                "status": "success",
                "trade_executed": True,
                "order_details": result,
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "error",
                "trade_executed": False,
                "message": "Trade execution failed",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error executing trade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/account-info")
async def get_account_info():
    """Get account information"""
    try:
        async with SchwabAPI() as schwab_api:
            account_info = await schwab_api.get_account_info()
            
            if account_info:
                return {
                    "status": "success",
                    "account_info": account_info,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=404, detail="Account information not available")
                
    except Exception as e:
        logger.error(f"Error getting account info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/positions")
async def get_positions():
    """Get current positions"""
    try:
        async with SchwabAPI() as schwab_api:
            positions = await schwab_api.get_positions()
            
            return {
                "status": "success",
                "positions": positions or [],
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/daily-report")
async def get_daily_report():
    """Get daily P&L and compliance report"""
    try:
        report = await trade_executor.generate_daily_report()
        
        return {
            "status": "success",
            "report": report,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating daily report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize-strategy")
async def optimize_strategy():
    """Trigger AI optimization for strategy parameters"""
    try:
        # This would implement the optimization layer
        # For now, return a placeholder response
        return {
            "status": "success",
            "message": "Strategy optimization triggered",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error optimizing strategy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Validate configuration
    if not config.validate_config():
        missing_config = config.get_missing_config()
        logger.error(f"Missing configuration: {missing_config}")
        print(f"Missing configuration: {missing_config}")
        print("Please check your .env file and ensure all required fields are set.")
        exit(1)
    
    # Start the server
    uvicorn.run(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.DEBUG,
        log_level=config.LOG_LEVEL.lower()
    )

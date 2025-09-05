"""Market data API endpoints for accessing processed market data.

Provides REST API for accessing real-time and historical market data
including 5-second bars, aggregated bars, and market metrics.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

from ..services.market_data_processor import market_data_processor
from ..services.trading_engine import trading_engine
from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-data", tags=["market-data"])


class BarDataRequest(BaseModel):
    """Request model for bar data."""
    symbol: str = Field(..., description="Stock symbol")
    count: int = Field(100, description="Number of bars to retrieve", ge=1, le=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "count": 100
            }
        }


class MarketDataSubscription(BaseModel):
    """Market data subscription request."""
    symbol: str = Field(..., description="Stock symbol")
    data_type: str = Field("bars", description="Data type: bars, snapshot, or both")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "data_type": "bars"
            }
        }


@router.get("/bars/{symbol}")
async def get_bar_data(
    symbol: str,
    count: int = Query(100, description="Number of bars", ge=1, le=1000)
) -> Dict[str, Any]:
    """Get historical 5-second bar data for a symbol.
    
    Returns the most recent bars from the buffer.
    """
    try:
        bars = await market_data_processor.get_buffer_data(symbol, count)
        
        return {
            "symbol": symbol,
            "count": len(bars),
            "bars": bars
        }
        
    except Exception as e:
        logger.error(f"Error fetching bar data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/bars/{symbol}/aggregated")
async def get_aggregated_bars(symbol: str) -> Dict[str, Any]:
    """Get aggregated bars for multiple time periods.
    
    Returns 1-minute, 5-minute, and 15-minute aggregated bars.
    """
    try:
        aggregated = await market_data_processor.get_aggregated_bars(symbol)
        
        if not aggregated:
            raise HTTPException(
                status_code=404, 
                detail=f"No data available for symbol {symbol}"
            )
            
        return {
            "symbol": symbol,
            "aggregated_bars": aggregated
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching aggregated bars: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/subscribe")
async def subscribe_to_bars(request: MarketDataSubscription) -> Dict[str, Any]:
    """Subscribe to real-time 5-second bars for a symbol.
    
    This will start streaming 5-second bars via WebSocket.
    """
    try:
        # Subscribe through trading engine (which connects to TWS)
        result = await trading_engine.subscribe_realtime_bars(request.symbol)
        
        return {
            **result,
            "message": "Subscribed to 5-second bars. Data will stream via WebSocket."
        }
        
    except TradingException as e:
        logger.error(f"Subscription failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in subscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/subscribe/{symbol}")
async def unsubscribe_from_bars(symbol: str) -> Dict[str, Any]:
    """Unsubscribe from real-time bar data."""
    try:
        result = await trading_engine.unsubscribe_market_data(symbol)
        
        return {
            **result,
            "message": "Unsubscribed from market data"
        }
        
    except TradingException as e:
        logger.error(f"Unsubscription failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in unsubscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/processor/status")
async def get_processor_status() -> Dict[str, Any]:
    """Get market data processor status.
    
    Returns information about tracked symbols, buffer sizes, and subscriptions.
    """
    try:
        status = market_data_processor.get_status()
        return status
        
    except Exception as e:
        logger.error(f"Error fetching processor status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/snapshot/{symbol}")
async def get_market_snapshot(symbol: str) -> Dict[str, Any]:
    """Get current market data snapshot for a symbol.
    
    Returns the latest price, volume, and calculated metrics.
    """
    try:
        # Get from trading engine's cached data
        snapshot = trading_engine.get_market_data(symbol)
        
        if not snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"No snapshot available for {symbol}. Subscribe to market data first."
            )
            
        # Get latest bars from processor
        bars = await market_data_processor.get_buffer_data(symbol, 1)
        
        return {
            "symbol": symbol,
            "snapshot": snapshot,
            "latest_bar": bars[0] if bars else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market snapshot: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics")
async def get_market_metrics(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols")
) -> Dict[str, Any]:
    """Get market metrics for one or more symbols.
    
    Returns calculated metrics including volatility, momentum, and volume analysis.
    """
    try:
        if symbols:
            symbol_list = symbols.split(",")
        else:
            # Get all tracked symbols
            status = market_data_processor.get_status()
            symbol_list = status.get("symbols_tracked", [])
            
        metrics = {}
        for symbol in symbol_list:
            bars = await market_data_processor.get_buffer_data(symbol, 1)
            if bars:
                # The processor calculates metrics with each bar
                # For now, return the latest bar data
                metrics[symbol] = bars[0]
                
        return {
            "metrics": metrics,
            "count": len(metrics)
        }
        
    except Exception as e:
        logger.error(f"Error fetching market metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
"""Trading API endpoints for order execution and market data.

Provides REST API for trading operations with <10ms latency target
for critical operations.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import logging

from ..services.trading_engine import trading_engine, OrderRequest
from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading", tags=["trading"])


class OrderRequestModel(BaseModel):
    """Order request model for API."""
    symbol: str = Field(..., description="Stock symbol")
    action: str = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, description="Number of shares")
    order_type: str = Field(..., description="MARKET or LIMIT")
    limit_price: Optional[float] = Field(None, description="Limit price for limit orders")
    stop_price: Optional[float] = Field(None, description="Stop price for stop orders")
    time_in_force: str = Field("GTC", description="Time in force (GTC, DAY, IOC)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 100,
                "order_type": "LIMIT",
                "limit_price": 185.50,
                "time_in_force": "GTC"
            }
        }


class CancelOrderRequest(BaseModel):
    """Cancel order request model."""
    order_id: int = Field(..., description="Order ID to cancel")


class MarketDataSubscription(BaseModel):
    """Market data subscription request."""
    symbol: str = Field(..., description="Stock symbol")
    data_type: str = Field("snapshot", description="Data type: snapshot or bars")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "data_type": "bars"
            }
        }


@router.post("/orders")
async def place_order(request: OrderRequestModel) -> Dict[str, Any]:
    """Place a new order.
    
    This is the critical trading path with <10ms latency target.
    """
    try:
        order_req = OrderRequest(
            symbol=request.symbol,
            action=request.action,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force
        )
        
        result = await trading_engine.place_order(order_req)
        return result
        
    except TradingException as e:
        logger.error(f"Order placement failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in order placement: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: int) -> Dict[str, Any]:
    """Cancel an existing order."""
    try:
        result = await trading_engine.cancel_order(order_id)
        return result
    except TradingException as e:
        logger.error(f"Order cancellation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in order cancellation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/orders")
async def get_orders(
    order_id: Optional[int] = Query(None, description="Specific order ID"),
    status: Optional[str] = Query(None, description="Filter by status")
) -> Any:
    """Get order information."""
    try:
        if order_id:
            order = trading_engine.get_order_status(order_id)
            if not order:
                raise HTTPException(status_code=404, detail="Order not found")
            return order
            
        # Get all orders
        orders = trading_engine.get_all_orders()
        
        # Filter by status if requested
        if status:
            orders = [o for o in orders if o["status"] == status]
            
        return {"orders": orders, "count": len(orders)}
        
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/positions")
async def get_positions() -> Dict[str, Any]:
    """Get all positions."""
    try:
        positions = trading_engine.get_positions()
        return {
            "positions": positions,
            "count": len(positions)
        }
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/market-data/subscribe")
async def subscribe_market_data(request: MarketDataSubscription) -> Dict[str, Any]:
    """Subscribe to market data for a symbol."""
    try:
        if request.data_type == "bars":
            result = await trading_engine.subscribe_realtime_bars(request.symbol)
        else:
            result = await trading_engine.subscribe_market_data(request.symbol)
        return result
    except TradingException as e:
        logger.error(f"Market data subscription failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in market data subscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/market-data/subscribe/{symbol}")
async def unsubscribe_market_data(symbol: str) -> Dict[str, Any]:
    """Unsubscribe from market data."""
    try:
        result = await trading_engine.unsubscribe_market_data(symbol)
        return result
    except TradingException as e:
        logger.error(f"Market data unsubscription failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in market data unsubscription: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/market-data")
async def get_market_data(
    symbol: Optional[str] = Query(None, description="Specific symbol or all")
) -> Dict[str, Any]:
    """Get current market data snapshot."""
    try:
        data = trading_engine.get_market_data(symbol)
        if symbol and not data:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return {"data": data, "timestamp": "utcnow"}
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """Get trading performance metrics."""
    try:
        metrics = trading_engine.get_performance_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error fetching performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_trading_status() -> Dict[str, Any]:
    """Get trading engine status."""
    try:
        status = trading_engine.get_status()
        return status
    except Exception as e:
        logger.error(f"Error fetching trading status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
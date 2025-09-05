"""Order management API endpoints.

Provides REST API for accessing order details, events, and executions.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
import logging

from ..services.order_manager import order_manager
from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orders", tags=["orders"])


class OrderEventsResponse(BaseModel):
    """Response model for order events."""
    order_id: int
    events: List[Dict[str, Any]]
    count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "order_id": 12345,
                "count": 5,
                "events": [
                    {
                        "order_id": 12345,
                        "event_type": "ORDER_CREATED",
                        "timestamp": "2024-01-05T10:30:00Z",
                        "status": "PENDING",
                        "message": "Order created",
                        "details": {}
                    }
                ]
            }
        }


class OrderExecutionsResponse(BaseModel):
    """Response model for order executions."""
    order_id: int
    executions: List[Dict[str, Any]]
    count: int
    total_quantity: int
    avg_price: float


@router.get("/{order_id}")
async def get_order_details(
    order_id: int = Path(..., description="Order ID")
) -> Dict[str, Any]:
    """Get detailed information for a specific order.
    
    Returns complete order details including all events and current status.
    """
    try:
        order = order_manager.get_order(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
            
        return {
            "order": order.to_dict(),
            "executions": [exec.to_dict() for exec in order_manager.get_executions(order_id)]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{order_id}/events")
async def get_order_events(
    order_id: int = Path(..., description="Order ID")
) -> OrderEventsResponse:
    """Get event history for an order.
    
    Returns all events that have occurred for this order.
    """
    try:
        events = order_manager.get_order_events(order_id)
        
        if not events:
            raise HTTPException(
                status_code=404, 
                detail=f"No events found for order {order_id}"
            )
            
        return OrderEventsResponse(
            order_id=order_id,
            events=[event.to_dict() for event in events],
            count=len(events)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order events: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{order_id}/executions")
async def get_order_executions(
    order_id: int = Path(..., description="Order ID")
) -> OrderExecutionsResponse:
    """Get execution reports for an order.
    
    Returns all executions (fills) that have occurred for this order.
    """
    try:
        executions = order_manager.get_executions(order_id)
        
        if not executions:
            # Check if order exists
            if not order_manager.get_order(order_id):
                raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
            
            # Order exists but no executions
            return OrderExecutionsResponse(
                order_id=order_id,
                executions=[],
                count=0,
                total_quantity=0,
                avg_price=0.0
            )
            
        # Calculate aggregates
        total_quantity = sum(exec.quantity for exec in executions)
        if total_quantity > 0:
            avg_price = sum(exec.price * exec.quantity for exec in executions) / total_quantity
        else:
            avg_price = 0.0
            
        return OrderExecutionsResponse(
            order_id=order_id,
            executions=[exec.to_dict() for exec in executions],
            count=len(executions),
            total_quantity=total_quantity,
            avg_price=round(avg_price, 2)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order executions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/active")
async def get_active_orders() -> Dict[str, Any]:
    """Get all active orders.
    
    Returns orders that are not filled, cancelled, or rejected.
    """
    try:
        active_orders = order_manager.get_active_orders()
        
        return {
            "orders": [order.to_dict() for order in active_orders],
            "count": len(active_orders)
        }
        
    except Exception as e:
        logger.error(f"Error fetching active orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/all")
async def get_all_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(100, description="Maximum number of orders", ge=1, le=1000)
) -> Dict[str, Any]:
    """Get all orders with optional filters.
    
    Returns a list of all orders, optionally filtered by status or symbol.
    """
    try:
        all_orders = order_manager.get_all_orders()
        
        # Apply filters
        if status:
            all_orders = [o for o in all_orders if o.status.value == status.upper()]
            
        if symbol:
            all_orders = [o for o in all_orders if o.symbol == symbol.upper()]
            
        # Apply limit
        all_orders = all_orders[:limit]
        
        return {
            "orders": [order.to_dict() for order in all_orders],
            "count": len(all_orders),
            "filters": {
                "status": status,
                "symbol": symbol,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching all orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/statistics")
async def get_order_statistics() -> Dict[str, Any]:
    """Get order manager statistics.
    
    Returns aggregate statistics about orders and executions.
    """
    try:
        stats = order_manager.get_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching order statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/manager/status")
async def get_order_manager_status() -> Dict[str, Any]:
    """Get order manager status.
    
    Returns the current status of the order manager service.
    """
    try:
        status = order_manager.get_status()
        return status
        
    except Exception as e:
        logger.error(f"Error fetching order manager status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
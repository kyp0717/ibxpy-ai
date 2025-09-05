"""Order manager service for tracking and managing order lifecycle.

This service handles order state management, event tracking, and
coordination between TWS callbacks and WebSocket broadcasting.
"""
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import logging

from ..core.config import settings
from ..core.exceptions import TradingException
from .websocket_service import websocket_service

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CANCELLED = "CANCELLED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"
    

class OrderAction(Enum):
    """Order action enumeration."""
    BUY = "BUY"
    SELL = "SELL"
    

class OrderType(Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass
class OrderEvent:
    """Order event for tracking state changes."""
    order_id: int
    event_type: str
    timestamp: datetime
    status: OrderStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['status'] = self.status.value
        return data


@dataclass
class OrderDetails:
    """Detailed order information."""
    order_id: int
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    limit_price: Optional[float]
    stop_price: Optional[float]
    filled_quantity: int
    remaining_quantity: int
    avg_fill_price: float
    last_fill_price: float
    status: OrderStatus
    submit_time: datetime
    last_update_time: datetime
    commission: float
    events: List[OrderEvent]
    execution_latency_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamps."""
        data = asdict(self)
        data['action'] = self.action.value
        data['order_type'] = self.order_type.value
        data['status'] = self.status.value
        data['submit_time'] = self.submit_time.isoformat()
        data['last_update_time'] = self.last_update_time.isoformat()
        data['events'] = [event.to_dict() for event in self.events]
        return data


@dataclass
class ExecutionReport:
    """Execution report for filled orders."""
    order_id: int
    exec_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float
    timestamp: datetime
    cumulative_quantity: int
    average_price: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class OrderManager:
    """Manages order lifecycle and state transitions."""
    
    def __init__(self):
        self._orders: Dict[int, OrderDetails] = {}
        self._executions: Dict[int, List[ExecutionReport]] = defaultdict(list)
        self._order_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._active_orders: set = set()
        self._running = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_processor_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the order manager."""
        if self._running:
            return
            
        self._running = True
        
        # Start event processor
        self._event_processor_task = asyncio.create_task(self._process_events())
        
        logger.info("Order manager started")
        
    async def stop(self):
        """Stop the order manager."""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel event processor
        if self._event_processor_task:
            self._event_processor_task.cancel()
            try:
                await self._event_processor_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Order manager stopped")
        
    async def create_order(self, 
                          order_id: int,
                          symbol: str,
                          action: str,
                          order_type: str,
                          quantity: int,
                          limit_price: Optional[float] = None,
                          stop_price: Optional[float] = None) -> OrderDetails:
        """Create a new order entry.
        
        Args:
            order_id: Unique order identifier
            symbol: Trading symbol
            action: BUY or SELL
            order_type: MARKET, LIMIT, STOP, STOP_LIMIT
            quantity: Order quantity
            limit_price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)
            
        Returns:
            OrderDetails object
        """
        now = datetime.utcnow()
        
        order = OrderDetails(
            order_id=order_id,
            symbol=symbol,
            action=OrderAction[action],
            order_type=OrderType[order_type],
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            filled_quantity=0,
            remaining_quantity=quantity,
            avg_fill_price=0.0,
            last_fill_price=0.0,
            status=OrderStatus.PENDING,
            submit_time=now,
            last_update_time=now,
            commission=0.0,
            events=[
                OrderEvent(
                    order_id=order_id,
                    event_type="ORDER_CREATED",
                    timestamp=now,
                    status=OrderStatus.PENDING,
                    message="Order created",
                    details={
                        "symbol": symbol,
                        "action": action,
                        "quantity": quantity
                    }
                )
            ]
        )
        
        self._orders[order_id] = order
        self._active_orders.add(order_id)
        
        # Queue event for processing
        await self._event_queue.put(("ORDER_CREATED", order))
        
        return order
        
    async def update_order_status(self,
                                 order_id: int,
                                 status: str,
                                 filled: int = 0,
                                 remaining: int = 0,
                                 avg_fill_price: float = 0.0,
                                 last_fill_price: float = 0.0,
                                 message: str = "") -> Optional[OrderDetails]:
        """Update order status from TWS callback.
        
        Args:
            order_id: Order identifier
            status: Status string from TWS
            filled: Filled quantity
            remaining: Remaining quantity
            avg_fill_price: Average fill price
            last_fill_price: Last fill price
            message: Optional status message
            
        Returns:
            Updated OrderDetails or None if order not found
        """
        if order_id not in self._orders:
            logger.warning(f"Order {order_id} not found for status update")
            return None
            
        order = self._orders[order_id]
        now = datetime.utcnow()
        
        # Map TWS status to our enum
        status_map = {
            "PendingSubmit": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.SUBMITTED,
            "Submitted": OrderStatus.SUBMITTED,
            "Filled": OrderStatus.FILLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Inactive": OrderStatus.CANCELLED,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Error": OrderStatus.ERROR
        }
        
        new_status = status_map.get(status, OrderStatus.ACKNOWLEDGED)
        
        # Check for partial fill
        if filled > 0 and filled < order.quantity:
            new_status = OrderStatus.PARTIALLY_FILLED
            
        # Update order details
        order.status = new_status
        order.filled_quantity = filled
        order.remaining_quantity = remaining
        order.avg_fill_price = avg_fill_price
        order.last_fill_price = last_fill_price
        order.last_update_time = now
        
        # Add event
        event = OrderEvent(
            order_id=order_id,
            event_type="STATUS_UPDATE",
            timestamp=now,
            status=new_status,
            message=message or f"Status changed to {new_status.value}",
            details={
                "filled": filled,
                "remaining": remaining,
                "avg_fill_price": avg_fill_price
            }
        )
        order.events.append(event)
        
        # Update active orders set
        if new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.ERROR]:
            self._active_orders.discard(order_id)
            
        # Queue event for processing
        await self._event_queue.put(("STATUS_UPDATE", order))
        
        return order
        
    async def add_execution(self,
                           order_id: int,
                           exec_id: str,
                           symbol: str,
                           side: str,
                           quantity: int,
                           price: float,
                           commission: float,
                           cumulative_quantity: int,
                           average_price: float) -> Optional[ExecutionReport]:
        """Add execution report for an order.
        
        Args:
            order_id: Order identifier
            exec_id: Execution identifier
            symbol: Trading symbol
            side: BOT or SLD
            quantity: Executed quantity
            price: Execution price
            commission: Commission amount
            cumulative_quantity: Total filled quantity
            average_price: Average fill price
            
        Returns:
            ExecutionReport or None if order not found
        """
        if order_id not in self._orders:
            logger.warning(f"Order {order_id} not found for execution report")
            return None
            
        order = self._orders[order_id]
        now = datetime.utcnow()
        
        execution = ExecutionReport(
            order_id=order_id,
            exec_id=exec_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=commission,
            timestamp=now,
            cumulative_quantity=cumulative_quantity,
            average_price=average_price
        )
        
        self._executions[order_id].append(execution)
        
        # Update order commission
        order.commission += commission
        order.last_update_time = now
        
        # Add execution event
        event = OrderEvent(
            order_id=order_id,
            event_type="EXECUTION",
            timestamp=now,
            status=order.status,
            message=f"Executed {quantity} @ {price}",
            details={
                "exec_id": exec_id,
                "quantity": quantity,
                "price": price,
                "commission": commission
            }
        )
        order.events.append(event)
        
        # Queue event for processing
        await self._event_queue.put(("EXECUTION", order, execution))
        
        return execution
        
    async def cancel_order(self, order_id: int) -> bool:
        """Mark order as cancel-pending.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if order found and marked for cancellation
        """
        if order_id not in self._orders:
            return False
            
        order = self._orders[order_id]
        now = datetime.utcnow()
        
        # Add cancellation event
        event = OrderEvent(
            order_id=order_id,
            event_type="CANCEL_REQUESTED",
            timestamp=now,
            status=order.status,
            message="Cancellation requested",
            details={}
        )
        order.events.append(event)
        order.last_update_time = now
        
        # Queue event for processing
        await self._event_queue.put(("CANCEL_REQUESTED", order))
        
        return True
        
    async def _process_events(self):
        """Process order events and broadcast updates."""
        while self._running:
            try:
                # Get event from queue with timeout
                event_data = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                event_type = event_data[0]
                order = event_data[1]
                
                # Broadcast order update
                await websocket_service.broadcast_order_update(
                    str(order.order_id),
                    {
                        "event_type": event_type,
                        "order": order.to_dict()
                    }
                )
                
                # Handle execution reports
                if event_type == "EXECUTION" and len(event_data) > 2:
                    execution = event_data[2]
                    await websocket_service.broadcast_market_data(
                        order.symbol,
                        {
                            "type": "execution",
                            "data": execution.to_dict()
                        }
                    )
                    
                # Trigger callbacks
                for callback in self._order_callbacks.get(event_type, []):
                    try:
                        await callback(order)
                    except Exception as e:
                        logger.error(f"Error in order callback: {e}")
                        
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing order event: {e}")
                
    def register_callback(self, event_type: str, callback: Callable):
        """Register a callback for order events.
        
        Args:
            event_type: Event type to listen for
            callback: Async function to call
        """
        self._order_callbacks[event_type].append(callback)
        
    def unregister_callback(self, event_type: str, callback: Callable):
        """Unregister a callback.
        
        Args:
            event_type: Event type
            callback: Callback to remove
        """
        if event_type in self._order_callbacks:
            if callback in self._order_callbacks[event_type]:
                self._order_callbacks[event_type].remove(callback)
                
    def get_order(self, order_id: int) -> Optional[OrderDetails]:
        """Get order details.
        
        Args:
            order_id: Order identifier
            
        Returns:
            OrderDetails or None if not found
        """
        return self._orders.get(order_id)
        
    def get_all_orders(self) -> List[OrderDetails]:
        """Get all orders.
        
        Returns:
            List of all OrderDetails
        """
        return list(self._orders.values())
        
    def get_active_orders(self) -> List[OrderDetails]:
        """Get active orders.
        
        Returns:
            List of active OrderDetails
        """
        return [self._orders[oid] for oid in self._active_orders if oid in self._orders]
        
    def get_executions(self, order_id: int) -> List[ExecutionReport]:
        """Get executions for an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            List of ExecutionReports
        """
        return self._executions.get(order_id, [])
        
    def get_order_events(self, order_id: int) -> List[OrderEvent]:
        """Get events for an order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            List of OrderEvents
        """
        order = self._orders.get(order_id)
        return order.events if order else []
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get order manager statistics.
        
        Returns:
            Statistics dictionary
        """
        total_orders = len(self._orders)
        active_orders = len(self._active_orders)
        
        status_counts = defaultdict(int)
        for order in self._orders.values():
            status_counts[order.status.value] += 1
            
        total_executions = sum(len(execs) for execs in self._executions.values())
        
        return {
            "total_orders": total_orders,
            "active_orders": active_orders,
            "status_breakdown": dict(status_counts),
            "total_executions": total_executions,
            "orders_with_executions": len(self._executions)
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get order manager status.
        
        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "statistics": self.get_statistics(),
            "event_queue_size": self._event_queue.qsize()
        }


# Global order manager instance
order_manager = OrderManager()
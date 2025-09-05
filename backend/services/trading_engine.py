"""Trading engine for order execution and market data management.

This engine coordinates between TWS service, WebSocket broadcasting, and 
maintains <10ms latency for critical trading operations.
"""
import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import logging

from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

from .tws_service import tws_service, ConnectionState
from .websocket_service import websocket_service
from .market_data_processor import market_data_processor
from .order_manager import order_manager
from .state_manager import state_manager, SystemState
from .connection_recovery import connection_recovery
from ..core.config import settings
from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """Order request data."""
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    order_type: str  # MARKET or LIMIT
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    
    
@dataclass
class OrderStatus:
    """Order status tracking."""
    order_id: int
    symbol: str
    action: str
    quantity: int
    filled_quantity: int
    remaining_quantity: int
    status: str
    avg_fill_price: float
    last_fill_price: float
    submit_time: datetime
    last_update_time: datetime
    
    
@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: float
    avg_cost: float
    unrealized_pnl: float
    realized_pnl: float
    market_value: float
    

@dataclass
class MarketDataSnapshot:
    """Market data snapshot."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    timestamp: datetime
    

@dataclass
class FiveSecondBar:
    """5-second bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float
    count: int


class TradingEngine:
    """Core trading engine for order execution and data management."""
    
    def __init__(self):
        self._orders: Dict[int, OrderStatus] = {}
        self._positions: Dict[str, Position] = {}
        self._market_data: Dict[str, MarketDataSnapshot] = {}
        self._subscriptions: Dict[str, int] = {}  # symbol -> req_id
        self._performance_metrics = {
            "total_orders": 0,
            "order_latencies": [],
            "data_latencies": []
        }
        self._running = False
        
    async def start(self):
        """Start the trading engine."""
        if self._running:
            logger.warning("Trading engine already running")
            return
            
        logger.info("Starting trading engine...")
        
        # Start market data processor
        await market_data_processor.start()
        logger.info("Market data processor started")
        
        # Start order manager
        await order_manager.start()
        logger.info("Order manager started")
        
        # Start state manager
        await state_manager.start()
        logger.info("State manager started")
        
        # Start connection recovery service
        await connection_recovery.start()
        logger.info("Connection recovery service started")
        
        # Connect to TWS
        connected = await tws_service.connect()
        if not connected:
            logger.error("Failed to connect to TWS")
            await state_manager.set_system_state(SystemState.ERROR)
            raise TradingException("TWS connection failed")
            
        self._running = True
        await state_manager.set_system_state(SystemState.CONNECTED)
        
        # Request initial positions
        await tws_service.request_positions()
        
        # Request account summary
        await tws_service.request_account_summary()
        
        logger.info("Trading engine started successfully")
        
    async def stop(self):
        """Stop the trading engine."""
        if not self._running:
            return
            
        logger.info("Stopping trading engine...")
        
        # Cancel all market data subscriptions
        for symbol, req_id in self._subscriptions.items():
            await tws_service.cancel_market_data(req_id)
            
        # Stop connection recovery service
        await connection_recovery.stop()
        logger.info("Connection recovery service stopped")
        
        # Stop state manager
        await state_manager.stop()
        logger.info("State manager stopped")
        
        # Stop order manager
        await order_manager.stop()
        logger.info("Order manager stopped")
        
        # Stop market data processor
        await market_data_processor.stop()
        logger.info("Market data processor stopped")
            
        # Disconnect from TWS
        await tws_service.disconnect()
        
        self._running = False
        logger.info("Trading engine stopped")
        
    async def place_order(self, request: OrderRequest) -> Dict[str, Any]:
        """Place an order with <10ms latency target.
        
        Args:
            request: Order request details
            
        Returns:
            Order confirmation with ID and latency
        """
        start_time = time.perf_counter()
        
        try:
            # Validate request
            if request.action not in ["BUY", "SELL"]:
                raise TradingException(f"Invalid action: {request.action}")
                
            if request.order_type not in ["MARKET", "LIMIT"]:
                raise TradingException(f"Invalid order type: {request.order_type}")
                
            if request.order_type == "LIMIT" and request.limit_price is None:
                raise TradingException("Limit price required for limit orders")
                
            # Create IB contract
            contract = tws_service.create_stock_contract(request.symbol)
            
            # Create IB order
            if request.order_type == "MARKET":
                ib_order = tws_service.create_market_order(
                    request.action, 
                    request.quantity
                )
            else:
                ib_order = tws_service.create_limit_order(
                    request.action,
                    request.quantity,
                    request.limit_price
                )
                
            # Create order in order manager first
            order_details = await order_manager.create_order(
                order_id=tws_service.wrapper.next_valid_id,
                symbol=request.symbol,
                action=request.action,
                order_type=request.order_type,
                quantity=request.quantity,
                limit_price=request.limit_price,
                stop_price=request.stop_price
            )
            
            # Place order (critical path - must be <10ms)
            order_id = await tws_service.place_order(contract, ib_order)
            
            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Update execution latency
            order_details.execution_latency_ms = latency_ms
            
            # Track order locally for backward compatibility
            order_status = OrderStatus(
                order_id=order_id,
                symbol=request.symbol,
                action=request.action,
                quantity=request.quantity,
                filled_quantity=0,
                remaining_quantity=request.quantity,
                status="SUBMITTED",
                avg_fill_price=0.0,
                last_fill_price=0.0,
                submit_time=datetime.utcnow(),
                last_update_time=datetime.utcnow()
            )
            self._orders[order_id] = order_status
            
            # Update metrics
            self._performance_metrics["total_orders"] += 1
            self._performance_metrics["order_latencies"].append(latency_ms)
            
            # Log performance warning if exceeded target
            if latency_ms > settings.max_latency_ms:
                logger.warning(f"Order latency {latency_ms:.2f}ms exceeded target {settings.max_latency_ms}ms")
            else:
                logger.info(f"Order placed in {latency_ms:.2f}ms")
                
            # Broadcast order update (non-critical path)
            await websocket_service.broadcast_order_update(
                str(order_id),
                {
                    "status": "SUBMITTED",
                    "symbol": request.symbol,
                    "action": request.action,
                    "quantity": request.quantity,
                    "latency_ms": latency_ms
                }
            )
            
            return {
                "order_id": order_id,
                "status": "SUBMITTED",
                "latency_ms": round(latency_ms, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Order placement failed: {e} (latency: {latency_ms:.2f}ms)")
            raise TradingException(f"Order placement failed: {e}")
            
    async def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            Cancellation confirmation
        """
        start_time = time.perf_counter()
        
        try:
            if order_id not in self._orders:
                raise TradingException(f"Order {order_id} not found")
                
            await tws_service.cancel_order(order_id)
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Update order status
            if order_id in self._orders:
                self._orders[order_id].status = "CANCEL_PENDING"
                self._orders[order_id].last_update_time = datetime.utcnow()
                
            # Broadcast update
            await websocket_service.broadcast_order_update(
                str(order_id),
                {"status": "CANCEL_PENDING", "latency_ms": latency_ms}
            )
            
            return {
                "order_id": order_id,
                "status": "CANCEL_PENDING",
                "latency_ms": round(latency_ms, 2)
            }
            
        except Exception as e:
            logger.error(f"Order cancellation failed: {e}")
            raise TradingException(f"Order cancellation failed: {e}")
            
    async def subscribe_market_data(self, symbol: str) -> Dict[str, Any]:
        """Subscribe to real-time market data for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Subscription confirmation
        """
        if symbol in self._subscriptions:
            return {"status": "already_subscribed", "symbol": symbol}
            
        contract = tws_service.create_stock_contract(symbol)
        
        # Define callback for market data updates
        async def on_market_data(data):
            snapshot = MarketDataSnapshot(
                symbol=symbol,
                bid=data.get("bid", 0),
                ask=data.get("ask", 0),
                last=data.get("last", 0),
                volume=data.get("volume", 0),
                timestamp=datetime.utcnow()
            )
            self._market_data[symbol] = snapshot
            
            # Broadcast to WebSocket clients
            await websocket_service.broadcast_market_data(
                symbol, 
                asdict(snapshot)
            )
            
        req_id = await tws_service.request_market_data(contract, on_market_data)
        self._subscriptions[symbol] = req_id
        
        return {
            "status": "subscribed",
            "symbol": symbol,
            "req_id": req_id
        }
        
    async def subscribe_realtime_bars(self, symbol: str) -> Dict[str, Any]:
        """Subscribe to 5-second bars for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Subscription confirmation
        """
        contract = tws_service.create_stock_contract(symbol)
        
        # Define callback for bar updates
        async def on_bar_update(bar_data):
            # Process bar through market data processor
            # This will handle aggregation, metrics, and broadcasting
            await market_data_processor.process_bar(symbol, {
                "timestamp": datetime.fromtimestamp(bar_data["time"]),
                "open": bar_data["open"],
                "high": bar_data["high"],
                "low": bar_data["low"],
                "close": bar_data["close"],
                "volume": bar_data["volume"],
                "wap": bar_data["wap"],
                "count": bar_data["count"]
            })
            
        req_id = await tws_service.request_realtime_bars(contract, on_bar_update)
        
        return {
            "status": "subscribed",
            "symbol": symbol,
            "req_id": req_id,
            "bar_type": "5_second"
        }
        
    async def unsubscribe_market_data(self, symbol: str) -> Dict[str, Any]:
        """Unsubscribe from market data.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Unsubscription confirmation
        """
        if symbol not in self._subscriptions:
            return {"status": "not_subscribed", "symbol": symbol}
            
        req_id = self._subscriptions[symbol]
        await tws_service.cancel_market_data(req_id)
        del self._subscriptions[symbol]
        
        if symbol in self._market_data:
            del self._market_data[symbol]
            
        return {
            "status": "unsubscribed",
            "symbol": symbol
        }
        
    def get_order_status(self, order_id: int) -> Optional[Dict[str, Any]]:
        """Get order status.
        
        Args:
            order_id: Order ID
            
        Returns:
            Order status or None if not found
        """
        if order_id in self._orders:
            return asdict(self._orders[order_id])
        return None
        
    def get_all_orders(self) -> List[Dict[str, Any]]:
        """Get all orders.
        
        Returns:
            List of all orders
        """
        return [asdict(order) for order in self._orders.values()]
        
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions.
        
        Returns:
            List of all positions
        """
        return [asdict(pos) for pos in self._positions.values()]
        
    def get_market_data(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get market data snapshot.
        
        Args:
            symbol: Specific symbol or None for all
            
        Returns:
            Market data
        """
        if symbol:
            if symbol in self._market_data:
                return asdict(self._market_data[symbol])
            return {}
        return {sym: asdict(data) for sym, data in self._market_data.items()}
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.
        
        Returns:
            Performance statistics
        """
        latencies = self._performance_metrics["order_latencies"]
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            
            # Calculate percentiles
            sorted_latencies = sorted(latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            p99_idx = int(len(sorted_latencies) * 0.99)
            
            p95 = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else max_latency
            p99 = sorted_latencies[p99_idx] if p99_idx < len(sorted_latencies) else max_latency
        else:
            avg_latency = min_latency = max_latency = p95 = p99 = 0
            
        return {
            "total_orders": self._performance_metrics["total_orders"],
            "order_latency_ms": {
                "avg": round(avg_latency, 2),
                "min": round(min_latency, 2),
                "max": round(max_latency, 2),
                "p95": round(p95, 2),
                "p99": round(p99, 2)
            },
            "active_subscriptions": len(self._subscriptions),
            "tracked_positions": len(self._positions)
        }
        
    def get_status(self) -> Dict[str, Any]:
        """Get trading engine status.
        
        Returns:
            Engine status information
        """
        return {
            "running": self._running,
            "tws_connection": tws_service.get_connection_status(),
            "active_orders": len([o for o in self._orders.values() if o.status not in ["FILLED", "CANCELLED"]]),
            "total_orders": len(self._orders),
            "positions": len(self._positions),
            "subscriptions": len(self._subscriptions),
            "performance": self.get_performance_metrics()
        }


# Global trading engine instance
trading_engine = TradingEngine()
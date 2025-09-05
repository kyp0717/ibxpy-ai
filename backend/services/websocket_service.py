"""WebSocket service for managing real-time data broadcasting.

This service acts as a bridge between the trading engine/market data
and WebSocket clients, handling message queuing and broadcasting.
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import msgpack

from ..api.websocket import manager as ws_manager
from ..core.config import settings

logger = logging.getLogger(__name__)


class WebSocketService:
    """Service for managing WebSocket communications."""
    
    def __init__(self):
        self.settings = settings
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
    async def start(self):
        """Start the WebSocket service."""
        if self._running:
            return
            
        self._running = True
        logger.info("Starting WebSocket service...")
        
        # Start the batch broadcaster
        await ws_manager.start_batch_broadcaster(
            batch_interval_ms=self.settings.batch_update_interval_ms
        )
        
        # Start heartbeat task
        self._tasks.append(
            asyncio.create_task(self._heartbeat_loop())
        )
        
        logger.info("WebSocket service started")
        
    async def stop(self):
        """Stop the WebSocket service."""
        if not self._running:
            return
            
        self._running = False
        logger.info("Stopping WebSocket service...")
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        logger.info("WebSocket service stopped")
        
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to all connected clients."""
        while self._running:
            try:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
                
                heartbeat_message = {
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                    "server_time": int(datetime.utcnow().timestamp() * 1000)
                }
                
                await ws_manager.broadcast(heartbeat_message)
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(1)
                
    async def broadcast_market_data(self, symbol: str, data: Dict[str, Any]):
        """Broadcast market data update for a symbol.
        
        Args:
            symbol: The trading symbol
            data: Market data to broadcast
        """
        message = {
            "type": "market_data",
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        # Use batch broadcasting for efficiency
        await ws_manager.queue_message(message)
        
    async def broadcast_order_update(self, order_id: str, update: Dict[str, Any]):
        """Broadcast order status update.
        
        Args:
            order_id: The order identifier
            update: Order update information
        """
        message = {
            "type": "order_update",
            "order_id": order_id,
            "timestamp": datetime.utcnow().isoformat(),
            "update": update
        }
        
        # Send immediately for order updates (critical)
        await ws_manager.broadcast(message)
        
    async def broadcast_position_update(self, account: str, positions: List[Dict[str, Any]]):
        """Broadcast position updates.
        
        Args:
            account: The account identifier
            positions: List of position updates
        """
        message = {
            "type": "position_update",
            "account": account,
            "timestamp": datetime.utcnow().isoformat(),
            "positions": positions
        }
        
        await ws_manager.broadcast(message)
        
    async def broadcast_alert(self, level: str, message: str, details: Optional[Dict] = None):
        """Broadcast system alert or notification.
        
        Args:
            level: Alert level (info, warning, error, critical)
            message: Alert message
            details: Optional additional details
        """
        alert_message = {
            "type": "alert",
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        }
        
        # Send alerts immediately
        await ws_manager.broadcast(alert_message)
        
    async def broadcast_five_second_bar(self, symbol: str, bar_data: Dict[str, Any]):
        """Broadcast 5-second bar data.
        
        Args:
            symbol: The trading symbol
            bar_data: 5-second bar OHLCV data
        """
        message = {
            "type": "five_second_bar",
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "bar": bar_data
        }
        
        # Queue for batch broadcasting
        await ws_manager.queue_message(message)
        
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return ws_manager.get_stats()


# Global WebSocket service instance
websocket_service = WebSocketService()
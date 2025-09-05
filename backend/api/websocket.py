"""WebSocket API endpoints for real-time communication.

This module provides WebSocket endpoints for streaming market data,
order updates, and position changes to connected clients.
"""
from typing import Dict, Set, Optional, Any
import json
import asyncio
from datetime import datetime
import msgpack

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi import Depends, status
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of symbols
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_task: Optional[asyncio.Task] = None
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        self.connection_metadata[client_id] = {
            "connected_at": datetime.utcnow().isoformat(),
            "message_count": 0,
            "last_ping": datetime.utcnow()
        }
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            del self.subscriptions[client_id]
            del self.connection_metadata[client_id]
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")
            
    async def send_personal_message(self, message: Any, client_id: str, binary: bool = True):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                websocket = self.active_connections[client_id]
                if binary:
                    await websocket.send_bytes(msgpack.packb(message))
                else:
                    await websocket.send_json(message)
                self.connection_metadata[client_id]["message_count"] += 1
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)
                
    async def broadcast(self, message: Any, symbol: Optional[str] = None):
        """Broadcast a message to all connected clients or those subscribed to a symbol."""
        if symbol:
            # Send only to clients subscribed to this symbol
            target_clients = [
                client_id for client_id, symbols in self.subscriptions.items()
                if symbol in symbols
            ]
        else:
            # Send to all connected clients
            target_clients = list(self.active_connections.keys())
            
        disconnected_clients = []
        for client_id in target_clients:
            try:
                await self.send_personal_message(message, client_id)
            except Exception as e:
                logger.error(f"Failed to send to {client_id}: {e}")
                disconnected_clients.append(client_id)
                
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            
    def add_subscription(self, client_id: str, symbol: str):
        """Add a symbol subscription for a client."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].add(symbol)
            logger.debug(f"Client {client_id} subscribed to {symbol}")
            
    def remove_subscription(self, client_id: str, symbol: str):
        """Remove a symbol subscription for a client."""
        if client_id in self.subscriptions:
            self.subscriptions[client_id].discard(symbol)
            logger.debug(f"Client {client_id} unsubscribed from {symbol}")
            
    async def start_batch_broadcaster(self, batch_interval_ms: int = 50):
        """Start the batch message broadcaster."""
        if self._broadcast_task and not self._broadcast_task.done():
            return
            
        async def batch_broadcast():
            """Batch and send messages at regular intervals."""
            pending_messages = []
            while True:
                try:
                    # Collect messages for batch_interval_ms
                    deadline = asyncio.get_event_loop().time() + (batch_interval_ms / 1000)
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            message = await asyncio.wait_for(
                                self._message_queue.get(),
                                timeout=max(0.001, deadline - asyncio.get_event_loop().time())
                            )
                            pending_messages.append(message)
                        except asyncio.TimeoutError:
                            break
                            
                    # Broadcast batched messages
                    if pending_messages:
                        batch_message = {
                            "type": "batch",
                            "timestamp": datetime.utcnow().isoformat(),
                            "messages": pending_messages
                        }
                        await self.broadcast(batch_message)
                        pending_messages.clear()
                        
                except Exception as e:
                    logger.error(f"Error in batch broadcaster: {e}")
                    await asyncio.sleep(0.1)
                    
        self._broadcast_task = asyncio.create_task(batch_broadcast())
        
    async def queue_message(self, message: Any):
        """Queue a message for batch broadcasting."""
        await self._message_queue.put(message)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.active_connections),
            "total_subscriptions": sum(len(subs) for subs in self.subscriptions.values()),
            "connections": {
                client_id: {
                    "subscriptions": list(self.subscriptions[client_id]),
                    **self.connection_metadata[client_id]
                }
                for client_id in self.active_connections
            }
        }


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/market")
async def websocket_market_data(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier"),
    binary: bool = Query(True, description="Use binary msgpack protocol")
):
    """WebSocket endpoint for real-time market data streaming.
    
    Supports both JSON and binary msgpack protocols.
    Binary mode is recommended for 3-5x performance improvement.
    
    Message types:
    - subscribe: Subscribe to symbol updates
    - unsubscribe: Unsubscribe from symbol updates
    - ping: Keep-alive message
    """
    await manager.connect(websocket, client_id)
    
    # Send initial connection message
    await manager.send_personal_message(
        {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "protocol": "msgpack" if binary else "json"
        },
        client_id,
        binary
    )
    
    try:
        while True:
            # Receive message from client
            if binary:
                data = await websocket.receive_bytes()
                message = msgpack.unpackb(data, raw=False)
            else:
                message = await websocket.receive_json()
                
            message_type = message.get("type")
            
            if message_type == "subscribe":
                symbols = message.get("symbols", [])
                for symbol in symbols:
                    manager.add_subscription(client_id, symbol)
                await manager.send_personal_message(
                    {
                        "type": "subscribed",
                        "symbols": symbols,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    client_id,
                    binary
                )
                
            elif message_type == "unsubscribe":
                symbols = message.get("symbols", [])
                for symbol in symbols:
                    manager.remove_subscription(client_id, symbol)
                await manager.send_personal_message(
                    {
                        "type": "unsubscribed",
                        "symbols": symbols,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    client_id,
                    binary
                )
                
            elif message_type == "ping":
                manager.connection_metadata[client_id]["last_ping"] = datetime.utcnow()
                await manager.send_personal_message(
                    {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    client_id,
                    binary
                )
                
            else:
                await manager.send_personal_message(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type}",
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    client_id,
                    binary
                )
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


@router.websocket("/orders")
async def websocket_order_updates(
    websocket: WebSocket,
    client_id: str = Query(..., description="Unique client identifier")
):
    """WebSocket endpoint for real-time order and position updates.
    
    Streams:
    - Order status changes
    - Fill notifications
    - Position updates
    - Account updates
    """
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Keep connection alive and handle client messages
            message = await websocket.receive_json()
            
            if message.get("type") == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": datetime.utcnow().isoformat()},
                    client_id,
                    binary=False
                )
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(client_id)


@router.get("/connections")
async def get_websocket_connections():
    """Get current WebSocket connection statistics."""
    return manager.get_stats()
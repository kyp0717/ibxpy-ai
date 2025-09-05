"""
Dependency injection for FastAPI
"""

from typing import AsyncGenerator, Optional
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import settings

logger = logging.getLogger(__name__)

# Optional security for future use
security = HTTPBearer(auto_error=False)


async def get_settings():
    """Dependency to get application settings"""
    return settings


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Verify API key if authentication is enabled
    Currently returns None (no auth required)
    """
    # TODO: Implement API key verification when needed
    return None


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: list = []
        self.connection_metadata: dict = {}
    
    async def connect(self, websocket, client_id: str = None):
        """Accept and track a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        if client_id:
            self.connection_metadata[websocket] = {"client_id": client_id}
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket):
        """Send message to specific WebSocket"""
        await websocket.send_text(message)
    
    async def send_personal_bytes(self, data: bytes, websocket):
        """Send binary data to specific WebSocket"""
        await websocket.send_bytes(data)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected WebSockets"""
        for connection in self.active_connections:
            await connection.send_text(message)
    
    async def broadcast_bytes(self, data: bytes):
        """Broadcast binary data to all connected WebSockets"""
        for connection in self.active_connections:
            await connection.send_bytes(data)
    
    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


async def get_connection_manager() -> ConnectionManager:
    """Dependency to get the connection manager"""
    return manager


# Performance monitoring
class PerformanceMonitor:
    """Monitor and track performance metrics"""
    
    def __init__(self):
        self.metrics = {
            "order_latency_ms": [],
            "data_latency_ms": [],
            "websocket_latency_ms": [],
            "api_latency_ms": []
        }
        self.max_samples = 1000
    
    def record_latency(self, metric_type: str, latency_ms: float):
        """Record a latency measurement"""
        if metric_type in self.metrics:
            self.metrics[metric_type].append(latency_ms)
            # Keep only the last max_samples
            if len(self.metrics[metric_type]) > self.max_samples:
                self.metrics[metric_type].pop(0)
    
    def get_stats(self, metric_type: str) -> dict:
        """Get statistics for a metric type"""
        if metric_type not in self.metrics or not self.metrics[metric_type]:
            return {"avg": 0, "min": 0, "max": 0, "p95": 0, "p99": 0}
        
        values = sorted(self.metrics[metric_type])
        n = len(values)
        
        return {
            "avg": sum(values) / n,
            "min": values[0],
            "max": values[-1],
            "p95": values[int(n * 0.95)] if n > 0 else 0,
            "p99": values[int(n * 0.99)] if n > 0 else 0,
            "count": n
        }
    
    def get_all_stats(self) -> dict:
        """Get statistics for all metrics"""
        return {
            metric: self.get_stats(metric)
            for metric in self.metrics.keys()
        }


# Global performance monitor
performance_monitor = PerformanceMonitor()


async def get_performance_monitor() -> PerformanceMonitor:
    """Dependency to get the performance monitor"""
    return performance_monitor
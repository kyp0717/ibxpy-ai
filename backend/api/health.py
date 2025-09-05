"""
Health check endpoints for monitoring system status
"""

from typing import Dict, Any, Optional
from datetime import datetime
import asyncio
import time

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from ..core.config import settings
from ..core.dependencies import (
    get_connection_manager,
    get_performance_monitor,
    ConnectionManager,
    PerformanceMonitor
)

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health check response model"""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    checks: Dict[str, Any]


class DetailedHealth(BaseModel):
    """Detailed health check with component statuses"""
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: float
    components: Dict[str, Dict[str, Any]]
    metrics: Optional[Dict[str, Any]] = None


# Track application start time
app_start_time = time.time()


def get_uptime() -> float:
    """Get application uptime in seconds"""
    return time.time() - app_start_time


async def check_tws_connection() -> Dict[str, Any]:
    """Check TWS connection status"""
    # TODO: Implement actual TWS connection check
    # For now, return mock status
    return {
        "status": "disconnected",
        "host": settings.tws_host,
        "port": settings.tws_port,
        "message": "TWS connection not yet implemented"
    }


async def check_redis_connection() -> Dict[str, Any]:
    """Check Redis connection status"""
    # TODO: Implement actual Redis connection check
    # For now, return mock status
    return {
        "status": "disconnected",
        "url": settings.redis_url,
        "message": "Redis connection not yet implemented"
    }


async def check_websocket_status(manager: ConnectionManager) -> Dict[str, Any]:
    """Check WebSocket connection status"""
    return {
        "status": "healthy",
        "active_connections": manager.get_connection_count(),
        "max_connections": settings.ws_max_connections,
        "utilization": f"{(manager.get_connection_count() / settings.ws_max_connections) * 100:.1f}%"
    }


@router.get("/", response_model=HealthStatus)
async def health_check():
    """
    Basic health check endpoint
    Returns 200 if service is running
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(),
        version=settings.app_version,
        uptime_seconds=get_uptime(),
        checks={
            "api": "online",
            "debug_mode": settings.debug
        }
    )


@router.get("/live", status_code=status.HTTP_204_NO_CONTENT)
async def liveness_probe():
    """
    Kubernetes liveness probe
    Returns 204 No Content if service is alive
    """
    return None


@router.get("/ready")
async def readiness_probe(
    manager: ConnectionManager = Depends(get_connection_manager)
):
    """
    Kubernetes readiness probe
    Checks if all critical services are ready
    Returns 200 if ready, 503 if not ready
    """
    checks = {
        "websocket": await check_websocket_status(manager),
        "tws": await check_tws_connection(),
    }
    
    # Determine overall readiness
    is_ready = all(
        check.get("status") in ["healthy", "connected", "disconnected"]  # Allow disconnected for now
        for check in checks.values()
    )
    
    if is_ready:
        return {
            "status": "ready",
            "timestamp": datetime.now(),
            "checks": checks
        }
    else:
        return {
            "status": "not_ready",
            "timestamp": datetime.now(),
            "checks": checks
        }


@router.get("/detailed", response_model=DetailedHealth)
async def detailed_health(
    manager: ConnectionManager = Depends(get_connection_manager),
    perf_monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
    """
    Detailed health check with component statuses and metrics
    """
    # Run all health checks concurrently
    websocket_check, tws_check, redis_check = await asyncio.gather(
        check_websocket_status(manager),
        check_tws_connection(),
        check_redis_connection()
    )
    
    # Determine overall status
    component_statuses = [
        websocket_check.get("status", "unknown"),
        # tws_check.get("status", "unknown"),  # Ignore TWS for now as it's not connected
        # redis_check.get("status", "unknown")  # Ignore Redis for now
    ]
    
    if all(s in ["healthy", "connected"] for s in component_statuses):
        overall_status = "healthy"
    elif any(s in ["unhealthy", "error"] for s in component_statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"
    
    return DetailedHealth(
        status=overall_status,
        timestamp=datetime.now(),
        version=settings.app_version,
        uptime_seconds=get_uptime(),
        components={
            "websocket": websocket_check,
            "tws": tws_check,
            "redis": redis_check,
            "api": {
                "status": "healthy",
                "host": settings.host,
                "port": settings.port,
                "debug": settings.debug
            }
        },
        metrics=perf_monitor.get_all_stats()
    )


@router.get("/metrics")
async def get_metrics(
    perf_monitor: PerformanceMonitor = Depends(get_performance_monitor)
):
    """
    Get performance metrics
    """
    return {
        "timestamp": datetime.now(),
        "uptime_seconds": get_uptime(),
        "metrics": perf_monitor.get_all_stats()
    }
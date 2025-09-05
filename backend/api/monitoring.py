"""Monitoring and error tracking API endpoints.

Provides REST API for system monitoring, error tracking,
and circuit breaker management.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
import logging

from ..core.error_handler import error_handler, ErrorSeverity
from ..services.trading_engine import trading_engine
from ..services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class ErrorSummaryResponse(BaseModel):
    """Response model for error summary."""
    total_errors: int
    error_types: int
    severity_breakdown: Dict[str, int]
    top_errors: List[tuple]
    circuit_breakers: Dict[str, Any]


class SystemHealthResponse(BaseModel):
    """Response model for system health."""
    status: str  # healthy, degraded, critical
    uptime_seconds: float
    error_rate: float
    active_connections: int
    system_state: str
    components: Dict[str, str]


@router.get("/errors")
async def get_recent_errors(
    count: int = Query(10, description="Number of errors to retrieve", ge=1, le=100),
    severity: Optional[str] = Query(None, description="Filter by severity")
) -> Dict[str, Any]:
    """Get recent errors from the system.
    
    Returns recent error occurrences with details and context.
    """
    try:
        severity_enum = None
        if severity:
            try:
                severity_enum = ErrorSeverity[severity.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid severity: {severity}. "
                           f"Valid values: {[e.value for e in ErrorSeverity]}"
                )
                
        errors = error_handler.get_recent_errors(count, severity_enum)
        
        return {
            "errors": errors,
            "count": len(errors),
            "filter": {"severity": severity} if severity else {}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching errors: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/errors/summary")
async def get_error_summary() -> ErrorSummaryResponse:
    """Get error summary statistics.
    
    Returns aggregate error statistics and circuit breaker states.
    """
    try:
        summary = error_handler.get_error_summary()
        
        return ErrorSummaryResponse(
            total_errors=summary["total_errors"],
            error_types=summary["error_types"],
            severity_breakdown=summary["severity_breakdown"],
            top_errors=summary["top_errors"],
            circuit_breakers=summary["circuit_breakers"]
        )
        
    except Exception as e:
        logger.error(f"Error fetching error summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/errors/clear")
async def clear_error_history() -> Dict[str, str]:
    """Clear all recorded errors.
    
    Resets error history but does not affect circuit breakers.
    """
    try:
        error_handler.clear_errors()
        
        return {
            "status": "success",
            "message": "Error history cleared"
        }
        
    except Exception as e:
        logger.error(f"Error clearing error history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/circuit-breakers")
async def get_circuit_breakers() -> Dict[str, Any]:
    """Get all circuit breaker states.
    
    Returns the current state of all circuit breakers in the system.
    """
    try:
        summary = error_handler.get_error_summary()
        
        return {
            "circuit_breakers": summary["circuit_breakers"],
            "count": len(summary["circuit_breakers"])
        }
        
    except Exception as e:
        logger.error(f"Error fetching circuit breakers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/circuit-breakers/{name}/reset")
async def reset_circuit_breaker(
    name: str = Path(..., description="Circuit breaker name")
) -> Dict[str, str]:
    """Reset a specific circuit breaker.
    
    Forces the circuit breaker back to CLOSED state.
    """
    try:
        error_handler.reset_circuit_breaker(name)
        
        return {
            "status": "success",
            "message": f"Circuit breaker '{name}' reset",
            "name": name
        }
        
    except Exception as e:
        logger.error(f"Error resetting circuit breaker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def get_system_health() -> SystemHealthResponse:
    """Get overall system health status.
    
    Returns comprehensive health metrics for monitoring.
    """
    try:
        # Get component statuses
        trading_status = trading_engine.get_status()
        state_status = state_manager.get_status()
        error_summary = error_handler.get_error_summary()
        
        # Calculate error rate (errors in last hour)
        total_errors = error_summary["total_errors"]
        critical_errors = error_summary["severity_breakdown"]["CRITICAL"]
        
        # Determine overall status
        if critical_errors > 0 or state_status["system_state"] == "ERROR":
            status = "critical"
        elif total_errors > 10:
            status = "degraded"
        else:
            status = "healthy"
            
        # Get uptime (simplified - would track actual start time in production)
        import time
        uptime = time.time() - 1704067200  # Placeholder start time
        
        return SystemHealthResponse(
            status=status,
            uptime_seconds=uptime,
            error_rate=total_errors / max(uptime / 3600, 1),  # Errors per hour
            active_connections=1 if trading_status["tws_connection"]["connected"] else 0,
            system_state=state_status["system_state"],
            components={
                "tws": "connected" if trading_status["tws_connection"]["connected"] else "disconnected",
                "trading_engine": "running" if trading_status["running"] else "stopped",
                "state_manager": "running" if state_status["running"] else "stopped",
                "websocket": "active",
                "api": "healthy"
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching system health: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """Get detailed system metrics.
    
    Returns performance metrics, resource usage, and throughput statistics.
    """
    try:
        trading_status = trading_engine.get_status()
        state_status = state_manager.get_status()
        error_summary = error_handler.get_error_summary()
        
        # Get performance metrics
        perf = trading_status.get("performance", {})
        
        return {
            "performance": {
                "order_latency_ms": perf.get("order_latency_ms", {}),
                "total_orders": perf.get("total_orders", 0),
                "active_subscriptions": perf.get("active_subscriptions", 0)
            },
            "errors": {
                "total": error_summary["total_errors"],
                "by_severity": error_summary["severity_breakdown"],
                "circuit_breakers_open": sum(
                    1 for cb in error_summary["circuit_breakers"].values()
                    if cb["state"] == "OPEN"
                )
            },
            "state": {
                "positions": state_status["position_count"],
                "accounts": state_status["account_count"],
                "risk_score": state_status["risk_score"]
            },
            "connections": {
                "tws": trading_status["tws_connection"]["connected"],
                "websocket_clients": 0  # Would get from websocket manager
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/alerts/test")
async def send_test_alert(
    level: str = Query("INFO", description="Alert level"),
    message: str = Query("Test alert", description="Alert message")
) -> Dict[str, Any]:
    """Send a test alert through the system.
    
    Useful for testing monitoring and alerting pipelines.
    """
    try:
        # Record as error for testing
        severity_map = {
            "INFO": ErrorSeverity.LOW,
            "WARNING": ErrorSeverity.MEDIUM,
            "ERROR": ErrorSeverity.HIGH,
            "CRITICAL": ErrorSeverity.CRITICAL
        }
        
        severity = severity_map.get(level.upper(), ErrorSeverity.LOW)
        
        error_handler.record_error(
            error_type="TEST_ALERT",
            message=message,
            severity=severity,
            context={"test": True, "level": level}
        )
        
        return {
            "status": "sent",
            "level": level,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
"""
Custom exceptions for the backend
"""

from typing import Any, Optional, Dict
from fastapi import HTTPException, status


class TradingException(Exception):
    """Base exception for trading-related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class TWSConnectionError(TradingException):
    """TWS connection-related errors"""
    pass


class OrderExecutionError(TradingException):
    """Order execution errors"""
    pass


class RiskLimitExceeded(TradingException):
    """Risk limit exceeded error"""
    pass


class MarketDataError(TradingException):
    """Market data related errors"""
    pass


class WebSocketError(TradingException):
    """WebSocket related errors"""
    pass


# HTTP Exceptions
def not_found(detail: str = "Resource not found") -> HTTPException:
    """404 Not Found exception"""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail
    )


def bad_request(detail: str = "Bad request") -> HTTPException:
    """400 Bad Request exception"""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail
    )


def unauthorized(detail: str = "Unauthorized") -> HTTPException:
    """401 Unauthorized exception"""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"}
    )


def forbidden(detail: str = "Forbidden") -> HTTPException:
    """403 Forbidden exception"""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail
    )


def internal_server_error(detail: str = "Internal server error") -> HTTPException:
    """500 Internal Server Error exception"""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail
    )


def service_unavailable(detail: str = "Service temporarily unavailable") -> HTTPException:
    """503 Service Unavailable exception"""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail
    )
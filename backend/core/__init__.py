"""
Core module for shared utilities
"""

from .config import settings
from .dependencies import ConnectionManager, PerformanceMonitor
from .exceptions import TradingException

__all__ = [
    "settings",
    "ConnectionManager",
    "PerformanceMonitor",
    "TradingException"
]
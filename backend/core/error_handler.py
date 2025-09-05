"""Error handling utilities and middleware.

Provides comprehensive error handling including retry logic,
circuit breaker pattern, and graceful degradation.
"""
import asyncio
import time
from typing import Callable, Optional, Any, Dict, List
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
import logging
import traceback

from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "LOW"        # Informational, no action needed
    MEDIUM = "MEDIUM"  # Warning, might need attention
    HIGH = "HIGH"      # Error, requires attention
    CRITICAL = "CRITICAL"  # System failure, immediate action needed


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"      # Circuit tripped, failing fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class ErrorRecord:
    """Record of an error occurrence."""
    
    def __init__(self, 
                 error_type: str,
                 message: str,
                 severity: ErrorSeverity,
                 context: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.severity = severity
        self.context = context or {}
        self.timestamp = datetime.utcnow()
        self.count = 1
        
    def increment(self):
        """Increment error count."""
        self.count += 1
        self.timestamp = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "count": self.count
        }


class CircuitBreaker:
    """Circuit breaker for preventing cascading failures."""
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitBreakerState.CLOSED
        
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise TradingException("Circuit breaker is OPEN")
                
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
            
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise TradingException("Circuit breaker is OPEN")
                
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
            
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        return (
            self.last_failure_time and
            datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
        )
        
    def reset(self):
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        
    def get_state(self) -> Dict[str, Any]:
        """Get circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


class RetryPolicy:
    """Retry policy for transient failures."""
    
    def __init__(self,
                 max_attempts: int = 3,
                 initial_delay: float = 1.0,
                 max_delay: float = 60.0,
                 exponential_base: float = 2.0,
                 jitter: bool = True):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(
            self.initial_delay * (self.exponential_base ** attempt),
            self.max_delay
        )
        
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())
            
        return delay


def with_retry(retry_policy: Optional[RetryPolicy] = None):
    """Decorator for adding retry logic to functions."""
    if retry_policy is None:
        retry_policy = RetryPolicy()
        
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_policy.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < retry_policy.max_attempts - 1:
                        delay = retry_policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {retry_policy.max_attempts} attempts failed for {func.__name__}"
                        )
                        
            raise last_exception
            
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(retry_policy.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < retry_policy.max_attempts - 1:
                        delay = retry_policy.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f} seconds..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {retry_policy.max_attempts} attempts failed for {func.__name__}"
                        )
                        
            raise last_exception
            
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


class ErrorHandler:
    """Global error handler for the trading system."""
    
    def __init__(self):
        self._errors: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._max_errors = 1000  # Maximum errors to keep in memory
        
    def record_error(self,
                    error_type: str,
                    message: str,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    context: Optional[Dict[str, Any]] = None):
        """Record an error occurrence."""
        # Find if we have a recent similar error
        for error in self._errors[-10:]:  # Check last 10 errors
            if error.error_type == error_type and error.message == message:
                error.increment()
                return
                
        # New error
        error = ErrorRecord(error_type, message, severity, context)
        self._errors.append(error)
        
        # Update count
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1
        
        # Trim if too many errors
        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]
            
        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(f"{error_type}: {message}")
        elif severity == ErrorSeverity.HIGH:
            logger.error(f"{error_type}: {message}")
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(f"{error_type}: {message}")
        else:
            logger.info(f"{error_type}: {message}")
            
    def get_circuit_breaker(self, 
                           name: str,
                           failure_threshold: int = 5,
                           recovery_timeout: int = 60) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self._circuit_breakers:
            self._circuit_breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return self._circuit_breakers[name]
        
    def get_recent_errors(self, 
                         count: int = 10,
                         severity: Optional[ErrorSeverity] = None) -> List[Dict[str, Any]]:
        """Get recent errors."""
        errors = self._errors
        
        if severity:
            errors = [e for e in errors if e.severity == severity]
            
        return [e.to_dict() for e in errors[-count:]]
        
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        severity_counts = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0
        }
        
        for error in self._errors:
            severity_counts[error.severity.value] += 1
            
        return {
            "total_errors": len(self._errors),
            "error_types": len(self._error_counts),
            "severity_breakdown": severity_counts,
            "top_errors": sorted(
                self._error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "circuit_breakers": {
                name: cb.get_state()
                for name, cb in self._circuit_breakers.items()
            }
        }
        
    def clear_errors(self):
        """Clear all recorded errors."""
        self._errors.clear()
        self._error_counts.clear()
        logger.info("Error history cleared")
        
    def reset_circuit_breaker(self, name: str):
        """Reset a specific circuit breaker."""
        if name in self._circuit_breakers:
            self._circuit_breakers[name].reset()
            logger.info(f"Circuit breaker '{name}' reset")


# Global error handler instance
error_handler = ErrorHandler()


async def handle_trading_error(error: Exception, context: Dict[str, Any]) -> Dict[str, Any]:
    """Handle trading-specific errors with appropriate responses."""
    error_type = type(error).__name__
    error_message = str(error)
    
    # Determine severity based on error type
    if isinstance(error, TradingException):
        severity = ErrorSeverity.HIGH
    elif "connection" in error_message.lower():
        severity = ErrorSeverity.CRITICAL
    elif "timeout" in error_message.lower():
        severity = ErrorSeverity.HIGH
    else:
        severity = ErrorSeverity.MEDIUM
        
    # Record error
    error_handler.record_error(
        error_type=error_type,
        message=error_message,
        severity=severity,
        context=context
    )
    
    # Return error response
    return {
        "error": True,
        "error_type": error_type,
        "message": error_message,
        "severity": severity.value,
        "timestamp": datetime.utcnow().isoformat(),
        "context": context
    }


def graceful_degradation(primary_func: Callable, 
                        fallback_func: Callable,
                        error_threshold: int = 3):
    """Decorator for graceful degradation to fallback function."""
    error_count = 0
    
    @wraps(primary_func)
    async def wrapper(*args, **kwargs):
        nonlocal error_count
        
        if error_count >= error_threshold:
            logger.warning(
                f"Using fallback for {primary_func.__name__} "
                f"after {error_count} errors"
            )
            return await fallback_func(*args, **kwargs)
            
        try:
            result = await primary_func(*args, **kwargs)
            error_count = 0  # Reset on success
            return result
        except Exception as e:
            error_count += 1
            logger.error(
                f"Error in {primary_func.__name__} "
                f"(attempt {error_count}): {e}"
            )
            
            if error_count >= error_threshold:
                return await fallback_func(*args, **kwargs)
            raise
            
    return wrapper
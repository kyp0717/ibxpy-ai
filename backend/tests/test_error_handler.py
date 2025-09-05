"""Tests for error handling and circuit breaker functionality."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from backend.core.error_handler import (
    ErrorHandler, ErrorSeverity, ErrorRecord,
    CircuitBreaker, CircuitBreakerState,
    RetryPolicy, with_retry,
    handle_trading_error
)
from backend.core.exceptions import TradingException


class TestErrorRecord:
    """Test ErrorRecord class."""
    
    def test_error_record_creation(self):
        """Test creating an error record."""
        error = ErrorRecord(
            error_type="TEST_ERROR",
            message="Test message",
            severity=ErrorSeverity.HIGH,
            context={"key": "value"}
        )
        
        assert error.error_type == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.severity == ErrorSeverity.HIGH
        assert error.context == {"key": "value"}
        assert error.count == 1
        assert isinstance(error.timestamp, datetime)
    
    def test_error_record_increment(self):
        """Test incrementing error count."""
        error = ErrorRecord(
            error_type="TEST_ERROR",
            message="Test message",
            severity=ErrorSeverity.LOW
        )
        
        original_count = error.count
        error.increment()
        
        assert error.count == original_count + 1
    
    def test_error_record_to_dict(self):
        """Test converting error record to dictionary."""
        error = ErrorRecord(
            error_type="TEST_ERROR",
            message="Test message",
            severity=ErrorSeverity.MEDIUM
        )
        
        data = error.to_dict()
        
        assert data["error_type"] == "TEST_ERROR"
        assert data["message"] == "Test message"
        assert data["severity"] == "MEDIUM"
        assert data["count"] == 1
        assert "timestamp" in data


class TestCircuitBreaker:
    """Test CircuitBreaker class."""
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Should allow calls when closed
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Fail 3 times to open the circuit
        for i in range(3):
            with pytest.raises(Exception):
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.failure_count == 3
    
    def test_circuit_breaker_rejects_when_open(self):
        """Test circuit breaker rejects calls when open."""
        cb = CircuitBreaker(failure_threshold=1)
        
        # Open the circuit
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        # Should reject calls when open
        with pytest.raises(TradingException) as exc_info:
            cb.call(lambda: "success")
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_async(self):
        """Test circuit breaker with async functions."""
        cb = CircuitBreaker(failure_threshold=2)
        
        async def success_func():
            return "success"
        
        async def fail_func():
            raise Exception("fail")
        
        # Success should work
        result = await cb.call_async(success_func)
        assert result == "success"
        
        # Failures should open circuit
        for i in range(2):
            with pytest.raises(Exception):
                await cb.call_async(fail_func)
        
        assert cb.state == CircuitBreakerState.OPEN
    
    def test_circuit_breaker_reset(self):
        """Test manually resetting circuit breaker."""
        cb = CircuitBreaker(failure_threshold=1)
        
        # Open the circuit
        with pytest.raises(Exception):
            cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Reset the circuit
        cb.reset()
        
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.last_failure_time is None


class TestRetryPolicy:
    """Test RetryPolicy class."""
    
    def test_retry_policy_delay_calculation(self):
        """Test retry delay calculation."""
        policy = RetryPolicy(
            initial_delay=1.0,
            exponential_base=2.0,
            max_delay=10.0,
            jitter=False
        )
        
        # Test exponential backoff
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(3) == 8.0
        assert policy.get_delay(4) == 10.0  # Capped at max_delay
        assert policy.get_delay(5) == 10.0  # Still capped
    
    def test_retry_policy_with_jitter(self):
        """Test retry delay with jitter."""
        policy = RetryPolicy(
            initial_delay=1.0,
            jitter=True
        )
        
        # With jitter, delay should be between 50% and 150% of base delay
        delay = policy.get_delay(0)
        assert 0.5 <= delay <= 1.5


class TestWithRetryDecorator:
    """Test with_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success(self):
        """Test retry decorator with successful function."""
        call_count = 0
        
        @with_retry(RetryPolicy(max_attempts=3, initial_delay=0.01))
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await success_func()
        
        assert result == "success"
        assert call_count == 1  # Should succeed on first try
    
    @pytest.mark.asyncio
    async def test_retry_decorator_eventual_success(self):
        """Test retry decorator with eventual success."""
        call_count = 0
        
        @with_retry(RetryPolicy(max_attempts=3, initial_delay=0.01))
        async def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("fail")
            return "success"
        
        result = await eventual_success()
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_max_attempts(self):
        """Test retry decorator reaches max attempts."""
        call_count = 0
        
        @with_retry(RetryPolicy(max_attempts=3, initial_delay=0.01))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("always fails")
        
        with pytest.raises(Exception) as exc_info:
            await always_fails()
        
        assert "always fails" in str(exc_info.value)
        assert call_count == 3


class TestErrorHandler:
    """Test ErrorHandler class."""
    
    def test_record_error(self):
        """Test recording errors."""
        handler = ErrorHandler()
        
        handler.record_error(
            error_type="TEST_ERROR",
            message="Test message",
            severity=ErrorSeverity.HIGH,
            context={"key": "value"}
        )
        
        errors = handler.get_recent_errors(count=10)
        assert len(errors) == 1
        assert errors[0]["error_type"] == "TEST_ERROR"
        assert errors[0]["severity"] == "HIGH"
    
    def test_error_deduplication(self):
        """Test error deduplication."""
        handler = ErrorHandler()
        
        # Record same error multiple times
        for i in range(5):
            handler.record_error(
                error_type="DUPLICATE_ERROR",
                message="Same message",
                severity=ErrorSeverity.LOW
            )
        
        errors = handler.get_recent_errors(count=10)
        
        # Should deduplicate and increment count
        duplicate_errors = [e for e in errors if e["error_type"] == "DUPLICATE_ERROR"]
        assert len(duplicate_errors) == 1
        assert duplicate_errors[0]["count"] == 5
    
    def test_error_summary(self):
        """Test error summary statistics."""
        handler = ErrorHandler()
        
        # Record various errors
        handler.record_error("ERROR1", "msg1", ErrorSeverity.LOW)
        handler.record_error("ERROR2", "msg2", ErrorSeverity.MEDIUM)
        handler.record_error("ERROR3", "msg3", ErrorSeverity.HIGH)
        handler.record_error("ERROR4", "msg4", ErrorSeverity.CRITICAL)
        
        summary = handler.get_error_summary()
        
        assert summary["total_errors"] == 4
        assert summary["error_types"] == 4
        assert summary["severity_breakdown"]["LOW"] == 1
        assert summary["severity_breakdown"]["MEDIUM"] == 1
        assert summary["severity_breakdown"]["HIGH"] == 1
        assert summary["severity_breakdown"]["CRITICAL"] == 1
    
    def test_clear_errors(self):
        """Test clearing error history."""
        handler = ErrorHandler()
        
        # Record some errors
        handler.record_error("ERROR1", "msg1", ErrorSeverity.HIGH)
        handler.record_error("ERROR2", "msg2", ErrorSeverity.LOW)
        
        # Clear errors
        handler.clear_errors()
        
        errors = handler.get_recent_errors(count=10)
        assert len(errors) == 0
        
        summary = handler.get_error_summary()
        assert summary["total_errors"] == 0
    
    def test_get_circuit_breaker(self):
        """Test getting circuit breaker."""
        handler = ErrorHandler()
        
        cb1 = handler.get_circuit_breaker("test_breaker")
        cb2 = handler.get_circuit_breaker("test_breaker")
        
        # Should return same instance
        assert cb1 is cb2
        
        # Should create new instance for different name
        cb3 = handler.get_circuit_breaker("another_breaker")
        assert cb3 is not cb1


class TestHandleTradingError:
    """Test handle_trading_error function."""
    
    @pytest.mark.asyncio
    async def test_handle_trading_exception(self):
        """Test handling TradingException."""
        error = TradingException("Trading error", {"detail": "test"})
        context = {"operation": "test_op"}
        
        result = await handle_trading_error(error, context)
        
        assert result["error"] is True
        assert result["error_type"] == "TradingException"
        assert result["message"] == "Trading error"
        assert result["severity"] == "HIGH"
        assert result["context"] == context
    
    @pytest.mark.asyncio
    async def test_handle_connection_error(self):
        """Test handling connection error."""
        error = Exception("Connection timeout")
        context = {"host": "localhost", "port": 7497}
        
        result = await handle_trading_error(error, context)
        
        assert result["error"] is True
        assert result["severity"] == "CRITICAL"
        assert "connection" in result["message"].lower()
    
    @pytest.mark.asyncio
    async def test_handle_timeout_error(self):
        """Test handling timeout error."""
        error = Exception("Request timeout")
        context = {"request": "market_data"}
        
        result = await handle_trading_error(error, context)
        
        assert result["error"] is True
        assert result["severity"] == "HIGH"
        assert "timeout" in result["message"].lower()
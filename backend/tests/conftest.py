"""Pytest configuration and fixtures for testing suite."""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import modules to test
from backend.main import app
from backend.services.tws_service import TWSService, ConnectionState
from backend.services.order_manager import OrderManager
from backend.services.state_manager import StateManager
from backend.services.market_data_processor import MarketDataProcessor
from backend.core.error_handler import ErrorHandler, CircuitBreaker


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> Generator:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_client() -> AsyncGenerator:
    """Create an async test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_tws_service():
    """Create a mock TWS service."""
    mock = Mock(spec=TWSService)
    mock.connection_state = ConnectionState.CONNECTED
    mock.connect = AsyncMock(return_value=True)
    mock.disconnect = AsyncMock()
    mock.place_order = AsyncMock(return_value=12345)
    mock.cancel_order = AsyncMock()
    mock.request_market_data = AsyncMock(return_value=1001)
    mock.get_connection_status = Mock(return_value={
        "state": "connected",
        "connected": True,
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 1,
        "next_order_id": 12345
    })
    return mock


@pytest.fixture
def mock_order_manager():
    """Create a mock order manager."""
    mock = Mock(spec=OrderManager)
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.create_order = AsyncMock(return_value={
        "order_id": 12345,
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "status": "PENDING"
    })
    mock.update_order_status = AsyncMock()
    mock.get_order = Mock(return_value={
        "order_id": 12345,
        "symbol": "AAPL",
        "status": "FILLED",
        "filled_quantity": 100
    })
    return mock


@pytest.fixture
def mock_state_manager():
    """Create a mock state manager."""
    mock = Mock(spec=StateManager)
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.update_position = AsyncMock()
    mock.update_account = AsyncMock()
    mock.get_position = Mock(return_value=None)
    mock.get_all_positions = Mock(return_value=[])
    mock.get_risk_metrics = Mock(return_value={
        "total_exposure": 0,
        "position_count": 0,
        "risk_score": 0
    })
    return mock


@pytest.fixture
def mock_market_data_processor():
    """Create a mock market data processor."""
    mock = Mock(spec=MarketDataProcessor)
    mock.start = AsyncMock()
    mock.stop = AsyncMock()
    mock.process_bar = AsyncMock()
    mock.get_latest_bar = Mock(return_value={
        "symbol": "AAPL",
        "timestamp": datetime.utcnow().isoformat(),
        "open": 150.0,
        "high": 151.0,
        "low": 149.0,
        "close": 150.5,
        "volume": 1000000
    })
    return mock


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler."""
    mock = Mock(spec=ErrorHandler)
    mock.record_error = Mock()
    mock.get_recent_errors = Mock(return_value=[])
    mock.get_error_summary = Mock(return_value={
        "total_errors": 0,
        "error_types": 0,
        "severity_breakdown": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
        "top_errors": [],
        "circuit_breakers": {}
    })
    mock.get_circuit_breaker = Mock(return_value=Mock(spec=CircuitBreaker))
    return mock


@pytest.fixture
def sample_order_request():
    """Sample order request data."""
    return {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "order_type": "LIMIT",
        "limit_price": 150.0
    }


@pytest.fixture
def sample_market_data():
    """Sample market data."""
    return {
        "symbol": "AAPL",
        "timestamp": datetime.utcnow().isoformat(),
        "open": 150.0,
        "high": 151.0,
        "low": 149.0,
        "close": 150.5,
        "volume": 1000000,
        "wap": 150.25,
        "count": 500
    }


@pytest.fixture
def sample_position():
    """Sample position data."""
    return {
        "symbol": "AAPL",
        "quantity": 100,
        "avg_cost": 149.50,
        "current_price": 150.50,
        "market_value": 15050.0,
        "unrealized_pnl": 100.0,
        "realized_pnl": 0.0,
        "account": "DU123456"
    }


@pytest.fixture
def sample_account():
    """Sample account data."""
    return {
        "account_id": "DU123456",
        "account_type": "CASH",
        "currency": "USD",
        "cash_balance": 100000.0,
        "total_value": 115050.0,
        "buying_power": 85000.0,
        "maintenance_margin": 0.0,
        "available_funds": 85000.0,
        "pnl_realized": 500.0,
        "pnl_unrealized": 100.0
    }
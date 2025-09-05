"""Tests for API endpoints."""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient

from backend.main import app


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint."""
        response = test_client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"
    
    def test_health_endpoint(self, test_client: TestClient):
        """Test health endpoint."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "uptime" in data
    
    def test_readiness_endpoint(self, test_client: TestClient):
        """Test readiness endpoint."""
        response = test_client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "components" in data


class TestTradingEndpoints:
    """Test trading API endpoints."""
    
    @patch('backend.api.trading.trading_engine')
    def test_place_order(self, mock_engine, test_client: TestClient):
        """Test placing an order."""
        mock_engine.place_order = AsyncMock(return_value={
            "order_id": 12345,
            "status": "PENDING"
        })
        
        order_data = {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MARKET"
        }
        
        response = test_client.post("/api/trading/orders", json=order_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == 12345
        assert data["status"] == "PENDING"
    
    @patch('backend.api.trading.trading_engine')
    def test_cancel_order(self, mock_engine, test_client: TestClient):
        """Test canceling an order."""
        mock_engine.cancel_order = AsyncMock(return_value={"status": "cancelled"})
        
        response = test_client.delete("/api/trading/orders/12345")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
    
    @patch('backend.api.trading.trading_engine')
    def test_subscribe_market_data(self, mock_engine, test_client: TestClient):
        """Test subscribing to market data."""
        mock_engine.subscribe_market_data = AsyncMock(return_value={
            "req_id": 1001,
            "status": "subscribed"
        })
        
        response = test_client.post("/api/trading/market-data/AAPL/subscribe")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "subscribed"


class TestOrderEndpoints:
    """Test order management endpoints."""
    
    @patch('backend.api.orders.order_manager')
    def test_get_all_orders(self, mock_manager, test_client: TestClient):
        """Test getting all orders."""
        mock_manager.get_all_orders = Mock(return_value=[
            {
                "order_id": 12345,
                "symbol": "AAPL",
                "status": "FILLED"
            }
        ])
        
        response = test_client.get("/api/orders")
        
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data
        assert len(data["orders"]) == 1
        assert data["orders"][0]["order_id"] == 12345
    
    @patch('backend.api.orders.order_manager')
    def test_get_order_by_id(self, mock_manager, test_client: TestClient):
        """Test getting order by ID."""
        mock_manager.get_order = Mock(return_value={
            "order_id": 12345,
            "symbol": "AAPL",
            "status": "FILLED",
            "filled_quantity": 100
        })
        
        response = test_client.get("/api/orders/12345")
        
        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == 12345
        assert data["status"] == "FILLED"
    
    @patch('backend.api.orders.order_manager')
    def test_get_order_not_found(self, mock_manager, test_client: TestClient):
        """Test getting non-existent order."""
        mock_manager.get_order = Mock(return_value=None)
        
        response = test_client.get("/api/orders/99999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestStateEndpoints:
    """Test state management endpoints."""
    
    @patch('backend.api.state.state_manager')
    def test_get_positions(self, mock_manager, test_client: TestClient):
        """Test getting positions."""
        mock_manager.get_all_positions = Mock(return_value=[])
        
        response = test_client.get("/api/state/positions")
        
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert "count" in data
        assert "total_unrealized_pnl" in data
    
    @patch('backend.api.state.state_manager')
    def test_get_risk_metrics(self, mock_manager, test_client: TestClient):
        """Test getting risk metrics."""
        mock_manager.get_risk_metrics = Mock(return_value={
            "total_exposure": 10000,
            "position_count": 2,
            "risk_score": 25.5,
            "margin_usage_percent": 30.0,
            "largest_position_symbol": "AAPL",
            "largest_position_value": 5000,
            "total_unrealized_pnl": 100,
            "total_realized_pnl": 200
        })
        
        response = test_client.get("/api/state/risk")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_exposure"] == 10000
        assert data["risk_score"] == 25.5


class TestMonitoringEndpoints:
    """Test monitoring endpoints."""
    
    @patch('backend.api.monitoring.error_handler')
    def test_get_errors(self, mock_handler, test_client: TestClient):
        """Test getting recent errors."""
        mock_handler.get_recent_errors = Mock(return_value=[
            {
                "error_type": "TEST_ERROR",
                "message": "Test message",
                "severity": "HIGH",
                "timestamp": "2024-01-01T00:00:00"
            }
        ])
        
        response = test_client.get("/api/monitoring/errors")
        
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error_type"] == "TEST_ERROR"
    
    @patch('backend.api.monitoring.error_handler')
    @patch('backend.api.monitoring.trading_engine')
    @patch('backend.api.monitoring.state_manager')
    def test_system_health(self, mock_state, mock_engine, mock_handler, test_client: TestClient):
        """Test system health endpoint."""
        mock_engine.get_status = Mock(return_value={
            "running": True,
            "tws_connection": {"connected": True},
            "performance": {}
        })
        mock_state.get_status = Mock(return_value={
            "running": True,
            "system_state": "CONNECTED"
        })
        mock_handler.get_error_summary = Mock(return_value={
            "total_errors": 0,
            "severity_breakdown": {"CRITICAL": 0}
        })
        
        response = test_client.get("/api/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["active_connections"] == 1
        assert "components" in data
    
    @patch('backend.api.monitoring.error_handler')
    def test_circuit_breakers(self, mock_handler, test_client: TestClient):
        """Test circuit breakers endpoint."""
        mock_handler.get_error_summary = Mock(return_value={
            "circuit_breakers": {
                "tws_connection": {
                    "state": "CLOSED",
                    "failure_count": 0
                }
            }
        })
        
        response = test_client.get("/api/monitoring/circuit-breakers")
        
        assert response.status_code == 200
        data = response.json()
        assert "circuit_breakers" in data
        assert "tws_connection" in data["circuit_breakers"]


class TestMarketDataEndpoints:
    """Test market data endpoints."""
    
    @patch('backend.api.market_data.market_data_processor')
    def test_get_latest_bar(self, mock_processor, test_client: TestClient):
        """Test getting latest bar data."""
        mock_processor.get_latest_bar = Mock(return_value={
            "symbol": "AAPL",
            "timestamp": "2024-01-01T00:00:00",
            "open": 150.0,
            "high": 151.0,
            "low": 149.0,
            "close": 150.5,
            "volume": 1000000
        })
        
        response = test_client.get("/api/market-data/AAPL/latest")
        
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["close"] == 150.5
    
    @patch('backend.api.market_data.market_data_processor')
    def test_get_aggregated_bars(self, mock_processor, test_client: TestClient):
        """Test getting aggregated bars."""
        mock_processor.get_aggregated_bars = Mock(return_value={
            "1min": [],
            "5min": [],
            "15min": []
        })
        
        response = test_client.get("/api/market-data/AAPL/bars?timeframe=5min&count=10")
        
        assert response.status_code == 200
        data = response.json()
        assert "bars" in data
        assert "count" in data
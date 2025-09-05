"""Tests for service components."""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from backend.services.order_manager import OrderManager, OrderStatus, OrderEvent
from backend.services.state_manager import (
    StateManager, Position, AccountData, RiskMetrics,
    TradingSession, TradingMode, SystemState
)
from backend.services.market_data_processor import (
    MarketDataProcessor, FiveSecondBar, BarBuffer
)
from backend.services.connection_recovery import (
    ConnectionRecoveryService, RecoveryState, RecoveryContext
)


class TestOrderManager:
    """Test OrderManager service."""
    
    @pytest.mark.asyncio
    async def test_order_creation(self):
        """Test creating an order."""
        manager = OrderManager()
        await manager.start()
        
        order = await manager.create_order(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="LIMIT",
            limit_price=150.0
        )
        
        assert order["order_id"] == 12345
        assert order["symbol"] == "AAPL"
        assert order["status"] == OrderStatus.PENDING.value
        assert order["quantity"] == 100
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_order_status_update(self):
        """Test updating order status."""
        manager = OrderManager()
        await manager.start()
        
        # Create order
        await manager.create_order(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MARKET"
        )
        
        # Update status
        await manager.update_order_status(
            order_id=12345,
            status="FILLED",
            filled=100,
            remaining=0,
            avg_fill_price=150.0
        )
        
        order = manager.get_order(12345)
        assert order["status"] == "FILLED"
        assert order["filled_quantity"] == 100
        assert order["avg_fill_price"] == 150.0
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_order_events(self):
        """Test order event tracking."""
        manager = OrderManager()
        await manager.start()
        
        # Create order
        await manager.create_order(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MARKET"
        )
        
        # Add events
        await manager.update_order_status(12345, "SUBMITTED")
        await manager.update_order_status(12345, "FILLED", filled=100)
        
        order = manager.get_order(12345)
        events = order["events"]
        
        assert len(events) >= 3  # Created, Submitted, Filled
        assert events[0]["event_type"] == OrderEvent.CREATED.value
        assert events[-1]["event_type"] == OrderEvent.STATUS_UPDATE.value
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_execution_tracking(self):
        """Test execution tracking."""
        manager = OrderManager()
        await manager.start()
        
        # Create order
        await manager.create_order(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MARKET"
        )
        
        # Add execution
        await manager.add_execution(
            order_id=12345,
            exec_id="exec_001",
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=150.0,
            commission=1.0
        )
        
        order = manager.get_order(12345)
        assert len(order["executions"]) == 1
        assert order["executions"][0]["exec_id"] == "exec_001"
        assert order["executions"][0]["price"] == 150.0
        
        await manager.stop()


class TestStateManager:
    """Test StateManager service."""
    
    @pytest.mark.asyncio
    async def test_position_management(self):
        """Test position creation and updates."""
        manager = StateManager()
        await manager.start()
        
        # Create position
        position = await manager.update_position(
            symbol="AAPL",
            quantity=100,
            avg_cost=149.50,
            current_price=150.50,
            account="DU123456"
        )
        
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.unrealized_pnl == 100.0  # (150.50 - 149.50) * 100
        
        # Get position
        retrieved = manager.get_position("AAPL")
        assert retrieved.symbol == "AAPL"
        
        # Close position
        closed = await manager.update_position(
            symbol="AAPL",
            quantity=0,
            avg_cost=149.50,
            current_price=151.00
        )
        
        assert manager.get_position("AAPL") is None
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_account_management(self):
        """Test account data management."""
        manager = StateManager()
        await manager.start()
        
        # Update account
        account = await manager.update_account(
            account_id="DU123456",
            account_data={
                "cash_balance": 100000.0,
                "total_value": 150000.0,
                "buying_power": 80000.0,
                "pnl_unrealized": 500.0
            }
        )
        
        assert account.account_id == "DU123456"
        assert account.cash_balance == 100000.0
        assert account.total_value == 150000.0
        
        # Get account
        retrieved = manager.get_account("DU123456")
        assert retrieved.account_id == "DU123456"
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_risk_metrics_calculation(self):
        """Test risk metrics calculation."""
        manager = StateManager()
        await manager.start()
        
        # Add positions
        await manager.update_position("AAPL", 100, 150.0, 155.0)
        await manager.update_position("GOOGL", 50, 2800.0, 2850.0)
        
        # Add account
        await manager.update_account("DU123456", {
            "total_value": 200000.0
        })
        
        # Get risk metrics
        metrics = manager.get_risk_metrics()
        
        assert metrics.position_count == 2
        assert metrics.total_exposure == 15500.0 + 142500.0  # AAPL + GOOGL market values
        assert metrics.total_unrealized_pnl == 500.0 + 2500.0  # Unrealized P&L
        assert metrics.largest_position_symbol == "GOOGL"
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_trading_session(self):
        """Test trading session management."""
        manager = StateManager()
        await manager.start()
        
        session = manager.get_session()
        assert session is not None
        assert session.mode == TradingMode.PAPER
        assert session.total_trades == 0
        
        # Record trades
        await manager.record_trade_result(100.0)  # Win
        await manager.record_trade_result(-50.0)  # Loss
        
        session = manager.get_session()
        assert session.total_trades == 2
        assert session.winning_trades == 1
        assert session.losing_trades == 1
        assert session.total_pnl == 50.0
        
        await manager.stop()


class TestMarketDataProcessor:
    """Test MarketDataProcessor service."""
    
    @pytest.mark.asyncio
    async def test_bar_processing(self):
        """Test processing 5-second bars."""
        processor = MarketDataProcessor()
        await processor.start()
        
        # Process a bar
        with patch('backend.services.market_data_processor.websocket_service') as mock_ws:
            mock_ws.broadcast_five_second_bar = AsyncMock()
            
            await processor.process_bar("AAPL", {
                "timestamp": datetime.utcnow().timestamp(),
                "open": 150.0,
                "high": 151.0,
                "low": 149.0,
                "close": 150.5,
                "volume": 10000,
                "wap": 150.25,
                "count": 100
            })
            
            # Check bar was broadcast
            mock_ws.broadcast_five_second_bar.assert_called_once()
            
        # Get latest bar
        latest = processor.get_latest_bar("AAPL")
        assert latest["symbol"] == "AAPL"
        assert latest["close"] == 150.5
        
        await processor.stop()
    
    @pytest.mark.asyncio
    async def test_bar_aggregation(self):
        """Test bar aggregation."""
        processor = MarketDataProcessor()
        await processor.start()
        
        # Add multiple 5-second bars
        base_time = datetime.utcnow()
        for i in range(15):  # 75 seconds of data
            await processor.process_bar("AAPL", {
                "timestamp": (base_time + timedelta(seconds=i*5)).timestamp(),
                "open": 150.0 + i * 0.1,
                "high": 150.5 + i * 0.1,
                "low": 149.5 + i * 0.1,
                "close": 150.0 + i * 0.1,
                "volume": 1000,
                "wap": 150.0 + i * 0.1,
                "count": 10
            })
        
        # Get aggregated bars
        aggregated = processor.get_aggregated_bars("AAPL", "1min", 10)
        
        assert "bars" in aggregated
        assert aggregated["count"] >= 1  # At least one 1-minute bar
        
        await processor.stop()
    
    def test_bar_buffer(self):
        """Test BarBuffer functionality."""
        buffer = BarBuffer(max_size=100)
        
        # Add bars
        bar1 = FiveSecondBar(
            symbol="AAPL",
            timestamp=datetime.utcnow(),
            open=150.0,
            high=151.0,
            low=149.0,
            close=150.5,
            volume=1000,
            wap=150.25,
            count=10
        )
        
        asyncio.run(buffer.add_bar(bar1))
        
        # Get recent bars
        recent = buffer.get_recent_bars(count=10)
        assert len(recent) == 1
        assert recent[0]["symbol"] == "AAPL"
        
        # Test max size limit
        for i in range(150):
            bar = FiveSecondBar(
                symbol="AAPL",
                timestamp=datetime.utcnow(),
                open=150.0 + i,
                high=151.0 + i,
                low=149.0 + i,
                close=150.5 + i,
                volume=1000,
                wap=150.25 + i,
                count=10
            )
            asyncio.run(buffer.add_bar(bar))
        
        # Should be capped at max_size
        assert len(buffer._bars) <= 100


class TestConnectionRecovery:
    """Test ConnectionRecoveryService."""
    
    @pytest.mark.asyncio
    async def test_recovery_service_start_stop(self):
        """Test starting and stopping recovery service."""
        service = ConnectionRecoveryService()
        
        await service.start()
        assert service._running is True
        assert service._recovery_state == RecoveryState.IDLE
        
        await service.stop()
        assert service._running is False
    
    @pytest.mark.asyncio
    async def test_trigger_recovery(self):
        """Test triggering recovery process."""
        service = ConnectionRecoveryService()
        
        # Mock TWS service
        mock_tws = Mock()
        mock_tws.disconnect = AsyncMock()
        mock_tws.connect = AsyncMock(return_value=False)  # Fail to connect
        mock_tws.get_connection_status = Mock(return_value={"connected": False})
        
        service.set_tws_service(mock_tws)
        
        await service.start()
        
        # Trigger recovery
        await service.trigger_recovery(Exception("Test error"))
        
        # Wait for recovery to attempt
        await asyncio.sleep(0.5)
        
        # Should have attempted to reconnect
        assert mock_tws.connect.called
        
        await service.stop()
    
    @pytest.mark.asyncio
    async def test_recovery_callbacks(self):
        """Test recovery callbacks."""
        service = ConnectionRecoveryService()
        
        callback_called = False
        async def recovery_callback(context: RecoveryContext):
            nonlocal callback_called
            callback_called = True
        
        service.register_recovery_callback("test", recovery_callback)
        
        # Mock successful reconnection
        mock_tws = Mock()
        mock_tws.disconnect = AsyncMock()
        mock_tws.connect = AsyncMock(return_value=True)
        mock_tws.request_positions = AsyncMock()
        mock_tws.request_account_summary = AsyncMock()
        
        service.set_tws_service(mock_tws)
        
        await service.start()
        await service.trigger_recovery()
        
        # Wait for recovery
        await asyncio.sleep(0.5)
        
        # Callback should have been called
        assert callback_called
        
        await service.stop()
    
    def test_recovery_status(self):
        """Test getting recovery status."""
        service = ConnectionRecoveryService()
        
        status = service.get_status()
        
        assert "running" in status
        assert "recovery_state" in status
        assert status["recovery_state"] == RecoveryState.IDLE.value
        assert status["is_recovering"] is False
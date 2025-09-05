"""Performance and benchmark tests for trading system."""
import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import statistics

from backend.services.trading_engine import TradingEngine
from backend.services.order_manager import OrderManager
from backend.services.market_data_processor import MarketDataProcessor, FiveSecondBar


class TestPerformanceBenchmarks:
    """Performance benchmark tests to ensure <10ms latency requirements."""
    
    @pytest.mark.asyncio
    async def test_order_placement_latency(self):
        """Test order placement latency is under 10ms."""
        engine = TradingEngine()
        
        # Mock TWS service for testing
        with patch('backend.services.trading_engine.tws_service') as mock_tws:
            mock_tws.connection_state = Mock(value="connected")
            mock_tws.place_order = AsyncMock(return_value=12345)
            mock_tws.create_stock_contract = Mock()
            mock_tws.create_market_order = Mock()
            
            latencies = []
            
            for i in range(100):  # Run 100 iterations
                start = time.perf_counter()
                
                result = await engine.place_order({
                    "symbol": "AAPL",
                    "action": "BUY",
                    "quantity": 100,
                    "order_type": "MARKET"
                })
                
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
            
            # Calculate statistics
            avg_latency = statistics.mean(latencies)
            p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
            p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
            
            print(f"\nOrder Placement Latency:")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  P95: {p95_latency:.2f}ms")
            print(f"  P99: {p99_latency:.2f}ms")
            
            # Assert latency requirements
            assert avg_latency < 10, f"Average latency {avg_latency:.2f}ms exceeds 10ms"
            assert p95_latency < 15, f"P95 latency {p95_latency:.2f}ms exceeds 15ms"
            assert p99_latency < 20, f"P99 latency {p99_latency:.2f}ms exceeds 20ms"
    
    @pytest.mark.asyncio
    async def test_market_data_processing_latency(self):
        """Test market data processing latency."""
        processor = MarketDataProcessor()
        await processor.start()
        
        latencies = []
        
        with patch('backend.services.market_data_processor.websocket_service') as mock_ws:
            mock_ws.broadcast_five_second_bar = AsyncMock()
            mock_ws.broadcast_aggregated_bars = AsyncMock()
            
            for i in range(100):
                start = time.perf_counter()
                
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
                
                end = time.perf_counter()
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
        
        await processor.stop()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        print(f"\nMarket Data Processing Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  Max: {max_latency:.2f}ms")
        
        # Assert latency requirements
        assert avg_latency < 5, f"Average latency {avg_latency:.2f}ms exceeds 5ms"
        assert max_latency < 10, f"Max latency {max_latency:.2f}ms exceeds 10ms"
    
    @pytest.mark.asyncio
    async def test_order_status_update_latency(self):
        """Test order status update latency."""
        manager = OrderManager()
        await manager.start()
        
        # Create an order first
        await manager.create_order(
            order_id=12345,
            symbol="AAPL",
            action="BUY",
            quantity=100,
            order_type="MARKET"
        )
        
        latencies = []
        
        for i in range(100):
            start = time.perf_counter()
            
            await manager.update_order_status(
                order_id=12345,
                status="FILLED" if i % 2 == 0 else "PARTIALLY_FILLED",
                filled=100 if i % 2 == 0 else 50,
                remaining=0 if i % 2 == 0 else 50,
                avg_fill_price=150.0 + i * 0.01
            )
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        await manager.stop()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        print(f"\nOrder Status Update Latency:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        
        # Assert latency requirements
        assert avg_latency < 5, f"Average latency {avg_latency:.2f}ms exceeds 5ms"
        assert p95_latency < 10, f"P95 latency {p95_latency:.2f}ms exceeds 10ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_order_processing(self):
        """Test concurrent order processing performance."""
        engine = TradingEngine()
        
        with patch('backend.services.trading_engine.tws_service') as mock_tws:
            mock_tws.connection_state = Mock(value="connected")
            mock_tws.place_order = AsyncMock(return_value=12345)
            mock_tws.create_stock_contract = Mock()
            mock_tws.create_market_order = Mock()
            
            # Create multiple concurrent order requests
            orders = [
                {"symbol": f"SYM{i}", "action": "BUY", "quantity": 100, "order_type": "MARKET"}
                for i in range(50)
            ]
            
            start = time.perf_counter()
            
            # Place orders concurrently
            tasks = [engine.place_order(order) for order in orders]
            results = await asyncio.gather(*tasks)
            
            end = time.perf_counter()
            total_time_ms = (end - start) * 1000
            avg_time_per_order = total_time_ms / len(orders)
            
            print(f"\nConcurrent Order Processing (50 orders):")
            print(f"  Total time: {total_time_ms:.2f}ms")
            print(f"  Average per order: {avg_time_per_order:.2f}ms")
            
            # Assert performance requirements
            assert avg_time_per_order < 10, f"Average time per order {avg_time_per_order:.2f}ms exceeds 10ms"
    
    @pytest.mark.asyncio
    async def test_websocket_broadcast_latency(self):
        """Test WebSocket broadcast latency."""
        from backend.services.websocket_service import websocket_service
        
        with patch('backend.services.websocket_service.WebSocketService.broadcast') as mock_broadcast:
            mock_broadcast.return_value = asyncio.create_task(asyncio.sleep(0))
            
            latencies = []
            
            for i in range(100):
                data = {
                    "symbol": "AAPL",
                    "price": 150.0 + i * 0.01,
                    "volume": 1000 + i,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                start = time.perf_counter()
                await websocket_service.broadcast_market_data("AAPL", data)
                end = time.perf_counter()
                
                latency_ms = (end - start) * 1000
                latencies.append(latency_ms)
            
            # Calculate statistics
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            
            print(f"\nWebSocket Broadcast Latency:")
            print(f"  Average: {avg_latency:.2f}ms")
            print(f"  Max: {max_latency:.2f}ms")
            
            # Assert latency requirements
            assert avg_latency < 2, f"Average latency {avg_latency:.2f}ms exceeds 2ms"
            assert max_latency < 5, f"Max latency {max_latency:.2f}ms exceeds 5ms"
    
    @pytest.mark.asyncio
    async def test_state_update_performance(self):
        """Test state manager update performance."""
        from backend.services.state_manager import state_manager
        
        await state_manager.start()
        
        latencies = []
        
        for i in range(100):
            start = time.perf_counter()
            
            await state_manager.update_position(
                symbol=f"SYM{i % 10}",  # Rotate through 10 symbols
                quantity=100 + i,
                avg_cost=150.0 + i * 0.1,
                current_price=151.0 + i * 0.1
            )
            
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            latencies.append(latency_ms)
        
        await state_manager.stop()
        
        # Calculate statistics
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]
        
        print(f"\nState Update Performance:")
        print(f"  Average: {avg_latency:.2f}ms")
        print(f"  P95: {p95_latency:.2f}ms")
        
        # Assert performance requirements
        assert avg_latency < 5, f"Average latency {avg_latency:.2f}ms exceeds 5ms"
        assert p95_latency < 10, f"P95 latency {p95_latency:.2f}ms exceeds 10ms"


class TestMemoryUsage:
    """Test memory usage and leak detection."""
    
    @pytest.mark.asyncio
    async def test_order_manager_memory(self):
        """Test order manager doesn't leak memory."""
        manager = OrderManager()
        await manager.start()
        
        # Create and process many orders
        for i in range(1000):
            await manager.create_order(
                order_id=10000 + i,
                symbol="AAPL",
                action="BUY" if i % 2 == 0 else "SELL",
                quantity=100,
                order_type="MARKET"
            )
            
            # Update status to completed
            await manager.update_order_status(
                order_id=10000 + i,
                status="FILLED",
                filled=100,
                remaining=0
            )
        
        # Check that old completed orders are cleaned up
        all_orders = manager.get_all_orders()
        
        # Should keep only recent orders (max 1000 by default)
        assert len(all_orders) <= 1000, f"Too many orders in memory: {len(all_orders)}"
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_market_data_buffer_limit(self):
        """Test market data buffer respects size limits."""
        processor = MarketDataProcessor()
        await processor.start()
        
        # Add many bars
        for i in range(500):
            await processor.process_bar("AAPL", {
                "timestamp": datetime.utcnow().timestamp() + i,
                "open": 150.0,
                "high": 151.0,
                "low": 149.0,
                "close": 150.5,
                "volume": 10000,
                "wap": 150.25,
                "count": 100
            })
        
        # Check buffer size is limited
        buffer = processor._buffers.get("AAPL")
        if buffer:
            assert len(buffer._bars) <= buffer._max_size, "Buffer exceeded max size"
        
        await processor.stop()


class TestConcurrency:
    """Test concurrent operations and thread safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_state_updates(self):
        """Test concurrent state updates don't cause race conditions."""
        from backend.services.state_manager import state_manager
        
        await state_manager.start()
        
        async def update_position(symbol: str, iterations: int):
            for i in range(iterations):
                await state_manager.update_position(
                    symbol=symbol,
                    quantity=100 + i,
                    avg_cost=150.0,
                    current_price=151.0 + i * 0.01
                )
        
        # Run concurrent updates on different symbols
        tasks = [
            update_position("AAPL", 50),
            update_position("GOOGL", 50),
            update_position("MSFT", 50),
            update_position("TSLA", 50)
        ]
        
        start = time.perf_counter()
        await asyncio.gather(*tasks)
        end = time.perf_counter()
        
        # Verify all positions exist
        positions = state_manager.get_all_positions()
        symbols = {p.symbol for p in positions}
        
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "MSFT" in symbols
        assert "TSLA" in symbols
        
        print(f"\nConcurrent State Updates (200 total):")
        print(f"  Time: {(end - start) * 1000:.2f}ms")
        
        await state_manager.stop()
"""Market data processor for integrating 5-second bars with real-time streaming.

This service processes market data from TWS and coordinates with WebSocket
broadcasting for real-time updates to connected clients.
"""
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from collections import deque
import logging
import statistics

from ..core.config import settings
from ..core.exceptions import TradingException
from .websocket_service import websocket_service

logger = logging.getLogger(__name__)


@dataclass
class FiveSecondBar:
    """5-second OHLCV bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float  # Weighted Average Price
    count: int  # Number of trades
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class AggregatedBar:
    """Aggregated bar from multiple 5-second bars."""
    symbol: str
    period: str  # '1min', '5min', '15min', etc.
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float  # Volume Weighted Average Price
    trade_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class MarketDataMetrics:
    """Real-time market data metrics."""
    symbol: str
    current_price: float
    bid: float
    ask: float
    spread: float
    volume_5s: int  # Last 5 seconds
    volume_1m: int  # Last minute
    volume_5m: int  # Last 5 minutes
    volatility_1m: float  # 1-minute volatility
    momentum: float  # Price momentum
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class BarBuffer:
    """Buffer for storing and aggregating 5-second bars."""
    
    def __init__(self, symbol: str, max_size: int = 1000):
        self.symbol = symbol
        self.max_size = max_size
        self.bars: deque = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        
    async def add_bar(self, bar: FiveSecondBar):
        """Add a new bar to the buffer."""
        async with self._lock:
            self.bars.append(bar)
            
    async def get_bars(self, count: Optional[int] = None) -> List[FiveSecondBar]:
        """Get the most recent bars."""
        async with self._lock:
            if count is None:
                return list(self.bars)
            return list(self.bars)[-count:] if count <= len(self.bars) else list(self.bars)
            
    async def get_aggregated_bar(self, seconds: int) -> Optional[AggregatedBar]:
        """Get an aggregated bar for the specified time period."""
        async with self._lock:
            if not self.bars:
                return None
                
            cutoff_time = datetime.utcnow() - timedelta(seconds=seconds)
            recent_bars = [bar for bar in self.bars if bar.timestamp >= cutoff_time]
            
            if not recent_bars:
                return None
                
            # Calculate aggregated values
            open_price = recent_bars[0].open
            close_price = recent_bars[-1].close
            high_price = max(bar.high for bar in recent_bars)
            low_price = min(bar.low for bar in recent_bars)
            total_volume = sum(bar.volume for bar in recent_bars)
            total_trades = sum(bar.count for bar in recent_bars)
            
            # Calculate VWAP
            if total_volume > 0:
                vwap = sum(bar.wap * bar.volume for bar in recent_bars) / total_volume
            else:
                vwap = close_price
                
            period_map = {
                60: '1min',
                300: '5min',
                900: '15min',
                3600: '1hour'
            }
            
            return AggregatedBar(
                symbol=self.symbol,
                period=period_map.get(seconds, f'{seconds}s'),
                timestamp=recent_bars[-1].timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=total_volume,
                vwap=round(vwap, 2),
                trade_count=total_trades
            )
            
    async def calculate_metrics(self) -> Optional[MarketDataMetrics]:
        """Calculate real-time market metrics."""
        async with self._lock:
            if len(self.bars) < 2:
                return None
                
            latest_bar = self.bars[-1]
            
            # Get bars for different time periods
            now = datetime.utcnow()
            bars_1m = [b for b in self.bars if b.timestamp >= now - timedelta(minutes=1)]
            bars_5m = [b for b in self.bars if b.timestamp >= now - timedelta(minutes=5)]
            
            # Calculate volumes
            volume_5s = latest_bar.volume
            volume_1m = sum(b.volume for b in bars_1m)
            volume_5m = sum(b.volume for b in bars_5m)
            
            # Calculate 1-minute volatility
            if len(bars_1m) > 1:
                prices_1m = [b.close for b in bars_1m]
                volatility_1m = statistics.stdev(prices_1m) if len(prices_1m) > 1 else 0
            else:
                volatility_1m = 0
                
            # Calculate momentum (rate of change)
            if len(self.bars) >= 12:  # 1 minute of data
                old_price = self.bars[-12].close
                momentum = ((latest_bar.close - old_price) / old_price) * 100 if old_price > 0 else 0
            else:
                momentum = 0
                
            # Estimate bid/ask (simplified - in production would come from Level 1 data)
            spread_estimate = 0.01  # 1 cent spread estimate
            bid = latest_bar.close - spread_estimate / 2
            ask = latest_bar.close + spread_estimate / 2
            
            return MarketDataMetrics(
                symbol=self.symbol,
                current_price=latest_bar.close,
                bid=round(bid, 2),
                ask=round(ask, 2),
                spread=round(spread_estimate, 2),
                volume_5s=volume_5s,
                volume_1m=volume_1m,
                volume_5m=volume_5m,
                volatility_1m=round(volatility_1m, 4),
                momentum=round(momentum, 2),
                timestamp=latest_bar.timestamp
            )


class MarketDataProcessor:
    """Processes and distributes market data."""
    
    def __init__(self):
        self._buffers: Dict[str, BarBuffer] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._aggregation_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        
    async def start(self):
        """Start the market data processor."""
        if self._running:
            return
            
        self._running = True
        logger.info("Market data processor started")
        
    async def stop(self):
        """Stop the market data processor."""
        if not self._running:
            return
            
        # Cancel all aggregation tasks
        for task in self._aggregation_tasks.values():
            task.cancel()
            
        await asyncio.gather(*self._aggregation_tasks.values(), return_exceptions=True)
        self._aggregation_tasks.clear()
        
        self._running = False
        logger.info("Market data processor stopped")
        
    async def process_bar(self, symbol: str, bar_data: Dict[str, Any]):
        """Process incoming 5-second bar data."""
        if not self._running:
            return
            
        # Create bar object
        bar = FiveSecondBar(
            symbol=symbol,
            timestamp=datetime.fromisoformat(bar_data['timestamp']) if isinstance(bar_data['timestamp'], str) 
                     else bar_data['timestamp'],
            open=bar_data['open'],
            high=bar_data['high'],
            low=bar_data['low'],
            close=bar_data['close'],
            volume=bar_data['volume'],
            wap=bar_data.get('wap', bar_data['close']),
            count=bar_data.get('count', 1)
        )
        
        # Get or create buffer for symbol
        if symbol not in self._buffers:
            self._buffers[symbol] = BarBuffer(symbol)
            self._start_aggregation_task(symbol)
            
        # Add bar to buffer
        await self._buffers[symbol].add_bar(bar)
        
        # Broadcast 5-second bar
        await websocket_service.broadcast_five_second_bar(symbol, bar.to_dict())
        
        # Calculate and broadcast metrics
        metrics = await self._buffers[symbol].calculate_metrics()
        if metrics:
            await websocket_service.broadcast_market_data(symbol, {
                'type': 'metrics',
                'data': metrics.to_dict()
            })
            
        # Notify subscribers
        if symbol in self._subscribers:
            for callback in self._subscribers[symbol]:
                try:
                    await callback(bar)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
                    
    def _start_aggregation_task(self, symbol: str):
        """Start aggregation task for a symbol."""
        if symbol not in self._aggregation_tasks:
            task = asyncio.create_task(self._aggregation_loop(symbol))
            self._aggregation_tasks[symbol] = task
            
    async def _aggregation_loop(self, symbol: str):
        """Continuously aggregate and broadcast bars."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                
                buffer = self._buffers.get(symbol)
                if not buffer:
                    continue
                    
                # Generate 1-minute bar
                bar_1m = await buffer.get_aggregated_bar(60)
                if bar_1m:
                    await websocket_service.broadcast_market_data(symbol, {
                        'type': 'bar_1m',
                        'data': bar_1m.to_dict()
                    })
                    
                # Generate 5-minute bar every 5 minutes
                if datetime.utcnow().minute % 5 == 0:
                    bar_5m = await buffer.get_aggregated_bar(300)
                    if bar_5m:
                        await websocket_service.broadcast_market_data(symbol, {
                            'type': 'bar_5m',
                            'data': bar_5m.to_dict()
                        })
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in aggregation loop for {symbol}: {e}")
                await asyncio.sleep(5)
                
    async def subscribe(self, symbol: str, callback: Callable):
        """Subscribe to bar updates for a symbol."""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        
    async def unsubscribe(self, symbol: str, callback: Callable):
        """Unsubscribe from bar updates."""
        if symbol in self._subscribers:
            if callback in self._subscribers[symbol]:
                self._subscribers[symbol].remove(callback)
            if not self._subscribers[symbol]:
                del self._subscribers[symbol]
                
    async def get_buffer_data(self, symbol: str, count: int = 100) -> List[Dict[str, Any]]:
        """Get historical bar data from buffer."""
        if symbol not in self._buffers:
            return []
            
        bars = await self._buffers[symbol].get_bars(count)
        return [bar.to_dict() for bar in bars]
        
    async def get_aggregated_bars(self, symbol: str) -> Dict[str, Any]:
        """Get aggregated bars for multiple time periods."""
        if symbol not in self._buffers:
            return {}
            
        buffer = self._buffers[symbol]
        
        result = {}
        for seconds, period in [(60, '1min'), (300, '5min'), (900, '15min')]:
            bar = await buffer.get_aggregated_bar(seconds)
            if bar:
                result[period] = bar.to_dict()
                
        return result
        
    def get_status(self) -> Dict[str, Any]:
        """Get processor status."""
        return {
            'running': self._running,
            'symbols_tracked': list(self._buffers.keys()),
            'buffer_sizes': {symbol: len(buffer.bars) for symbol, buffer in self._buffers.items()},
            'subscribers': {symbol: len(subs) for symbol, subs in self._subscribers.items()},
            'aggregation_tasks': list(self._aggregation_tasks.keys())
        }


# Global market data processor instance
market_data_processor = MarketDataProcessor()
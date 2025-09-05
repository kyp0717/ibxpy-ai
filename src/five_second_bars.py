"""
Five-Second Bar Data Module
Stage 02, Phase 01 - Retrieve 5-Second Bar Data from TWS
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any, Deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

try:
    from ibapi.contract import Contract
    from ibapi.common import BarData
except ImportError:
    raise ImportError(
        "ibapi package not found. Please install it using the install_ibapi.sh script"
    )

from connection import TWSConnection

logger = logging.getLogger(__name__)


@dataclass
class FiveSecondBar:
    """Data class for storing 5-second bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float = 0.0  # Weighted average price
    count: int = 0
    
    def __str__(self) -> str:
        return (f"5s Bar [{self.timestamp.strftime('%H:%M:%S')}] "
                f"O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} "
                f"C:{self.close:.2f} V:{self.volume}")


@dataclass
class BarBuffer:
    """Buffer to store and manage 5-second bars"""
    max_size: int = 1000  # Keep last 1000 bars (about 1.4 hours of data)
    bars: Deque[FiveSecondBar] = field(default_factory=deque)
    
    def add_bar(self, bar: FiveSecondBar) -> None:
        """Add a bar to the buffer, removing oldest if at capacity"""
        if len(self.bars) >= self.max_size:
            self.bars.popleft()
        self.bars.append(bar)
    
    def get_latest(self, n: int = 1) -> List[FiveSecondBar]:
        """Get the n most recent bars"""
        if n >= len(self.bars):
            return list(self.bars)
        return list(self.bars)[-n:]
    
    def get_bars_since(self, timestamp: datetime) -> List[FiveSecondBar]:
        """Get all bars since a given timestamp"""
        return [bar for bar in self.bars if bar.timestamp >= timestamp]
    
    def clear(self) -> None:
        """Clear all bars from buffer"""
        self.bars.clear()


class FiveSecondBarClient(TWSConnection):
    """Client for handling 5-second bar data operations"""
    
    def __init__(self):
        super().__init__()
        self.bar_buffer = BarBuffer()
        self.latest_bar: Optional[FiveSecondBar] = None
        self._bar_received_event = threading.Event()
        self._streaming_active = False
        self._current_req_id: Optional[int] = None
        self._next_request_id = 1000  # Start from 1000 to avoid conflicts
        self._bar_count = 0
        self._error_count = 0
        
    def get_next_request_id(self) -> int:
        """Get the next request ID for API calls"""
        req_id = self._next_request_id
        self._next_request_id += 1
        return req_id
    
    def realtimeBar(self, reqId: int, time: int, open_: float, high: float, 
                    low: float, close: float, volume: int, wap: float, count: int):
        """Handle incoming 5-second real-time bar data"""
        bar_time = datetime.fromtimestamp(time)
        
        five_second_bar = FiveSecondBar(
            timestamp=bar_time,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            wap=wap,
            count=count
        )
        
        # Store the bar
        self.bar_buffer.add_bar(five_second_bar)
        self.latest_bar = five_second_bar
        self._bar_count += 1
        
        # Log the bar
        logger.debug(f"Received {five_second_bar}")
        
        # Signal that a bar was received
        self._bar_received_event.set()
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors from TWS"""
        super().error(reqId, errorCode, errorString, advancedOrderRejectJson)
        
        # Track streaming-related errors
        if reqId == self._current_req_id:
            self._error_count += 1
            if errorCode == 200:  # No security definition found
                logger.error(f"Invalid symbol or security definition not found")
                self._streaming_active = False
            elif errorCode == 162:  # Historical data service error
                logger.error(f"Historical/realtime data service error")
                self._streaming_active = False
    
    def start_5second_streaming(self, symbol: str, exchange: str = "SMART", 
                               currency: str = "USD") -> bool:
        """Start streaming 5-second bars for a symbol"""
        if self._streaming_active:
            logger.warning(f"Already streaming 5-second bars for a symbol")
            return False
        
        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = exchange
        contract.currency = currency
        
        # Get request ID
        self._current_req_id = self.get_next_request_id()
        
        logger.info(f"Starting 5-second bar streaming for {symbol} (reqId: {self._current_req_id})")
        
        try:
            # Request real-time bars
            self.reqRealTimeBars(
                reqId=self._current_req_id,
                contract=contract,
                barSize=5,  # 5-second bars
                whatToShow="TRADES",
                useRTH=False,  # Include pre/post market
                realTimeBarsOptions=[]
            )
            
            self._streaming_active = True
            self._bar_count = 0
            self._error_count = 0
            
            # Wait briefly to check if streaming started successfully
            if self._bar_received_event.wait(timeout=10):
                logger.info(f"Successfully started 5-second bar streaming for {symbol}")
                return True
            else:
                logger.warning(f"No 5-second bars received within 10 seconds for {symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting 5-second bar streaming: {e}")
            self._streaming_active = False
            return False
    
    def stop_5second_streaming(self) -> bool:
        """Stop streaming 5-second bars"""
        if not self._streaming_active:
            logger.warning("No active 5-second bar streaming to stop")
            return False
        
        if self._current_req_id is not None:
            try:
                self.cancelRealTimeBars(self._current_req_id)
                logger.info(f"Stopped 5-second bar streaming (reqId: {self._current_req_id})")
                logger.info(f"Total bars received: {self._bar_count}, Errors: {self._error_count}")
            except Exception as e:
                logger.error(f"Error stopping 5-second bar streaming: {e}")
                return False
        
        self._streaming_active = False
        self._current_req_id = None
        return True
    
    def get_latest_bars(self, n: int = 10) -> List[FiveSecondBar]:
        """Get the n most recent 5-second bars"""
        return self.bar_buffer.get_latest(n)
    
    def get_bars_for_minute(self, minutes: int = 1) -> List[FiveSecondBar]:
        """Get all 5-second bars for the last n minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return self.bar_buffer.get_bars_since(cutoff_time)
    
    def wait_for_bars(self, count: int = 1, timeout: float = 30) -> bool:
        """Wait for a specific number of bars to be received"""
        start_count = self._bar_count
        start_time = time.time()
        
        while (self._bar_count - start_count) < count:
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout waiting for {count} bars")
                return False
            
            self._bar_received_event.wait(timeout=1)
            self._bar_received_event.clear()
        
        return True
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """Get current streaming status"""
        return {
            "streaming_active": self._streaming_active,
            "request_id": self._current_req_id,
            "bars_received": self._bar_count,
            "errors": self._error_count,
            "buffer_size": len(self.bar_buffer.bars),
            "latest_bar": str(self.latest_bar) if self.latest_bar else None
        }
    
    def clear_buffer(self) -> None:
        """Clear the bar buffer"""
        self.bar_buffer.clear()
        self._bar_count = 0
        logger.info("Cleared 5-second bar buffer")


def demonstrate_5second_bars():
    """Demonstration function for 5-second bar streaming"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    client = FiveSecondBarClient()
    
    try:
        # Connect to TWS
        logger.info("Connecting to TWS...")
        if not client.connect_to_tws():
            logger.error("Failed to connect to TWS")
            return
        
        # Start streaming 5-second bars for AAPL
        symbol = "AAPL"
        logger.info(f"Starting 5-second bar streaming for {symbol}...")
        
        if client.start_5second_streaming(symbol):
            # Wait for some bars to accumulate
            logger.info("Waiting for 5-second bars...")
            
            if client.wait_for_bars(count=6, timeout=35):  # Wait for 6 bars (30 seconds)
                # Display latest bars
                latest_bars = client.get_latest_bars(n=6)
                logger.info(f"\nLatest {len(latest_bars)} bars:")
                for bar in latest_bars:
                    print(f"  {bar}")
                
                # Show streaming status
                status = client.get_streaming_status()
                logger.info(f"\nStreaming Status:")
                for key, value in status.items():
                    print(f"  {key}: {value}")
            
            # Continue streaming for a bit longer
            time.sleep(10)
            
            # Stop streaming
            client.stop_5second_streaming()
        else:
            logger.error("Failed to start 5-second bar streaming")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Demonstration error: {e}")
    finally:
        # Clean up
        if client._streaming_active:
            client.stop_5second_streaming()
        client.disconnect()
        logger.info("Disconnected from TWS")


if __name__ == "__main__":
    demonstrate_5second_bars()
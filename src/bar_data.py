"""
Bar Data Module - Handles retrieving minute bar data and calculating EMAs
Phase 12 - Retrieve 1-Minute Bar Data and Calculate EMA
"""

import logging
import threading
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
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
class MinuteBar:
    """Data class for storing minute bar data"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    wap: float = 0.0  # Weighted average price
    count: int = 0
    
    def __str__(self) -> str:
        return f"Bar [{self.timestamp.strftime('%H:%M')}] O:{self.open:.2f} H:{self.high:.2f} L:{self.low:.2f} C:{self.close:.2f} V:{self.volume}"


class BarDataClient(TWSConnection):
    """Client for handling bar data operations"""
    
    def __init__(self):
        super().__init__()
        self.bars: List[MinuteBar] = []
        self.latest_bar: Optional[MinuteBar] = None
        self._bar_data_received = threading.Event()
        self._historical_data_end = threading.Event()
        self.ema_values: List[float] = []
        self.current_ema: Optional[float] = None
        self.ema_period: int = 9
        self.is_streaming: bool = False
        self._streaming_bars = deque(maxlen=100)  # Keep last 100 streaming bars
        self._next_request_id = 1
        
    def get_next_request_id(self) -> int:
        """Get the next request ID for API calls"""
        req_id = self._next_request_id
        self._next_request_id += 1
        return req_id
        
    def historicalData(self, reqId: int, bar: BarData):
        """Handle historical bar data"""
        logger.debug(f"Historical Bar: {bar.date} O:{bar.open} H:{bar.high} L:{bar.low} C:{bar.close} V:{bar.volume}")
        
        # Parse the bar data
        if ":" in bar.date:
            # Format is "YYYYMMDD HH:MM:SS"
            bar_time = datetime.strptime(bar.date, "%Y%m%d %H:%M:%S")
        else:
            # Format is "YYYYMMDD"
            bar_time = datetime.strptime(bar.date, "%Y%m%d")
            
        minute_bar = MinuteBar(
            timestamp=bar_time,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            wap=bar.wap if hasattr(bar, 'wap') else 0.0,
            count=bar.count if hasattr(bar, 'count') else 0
        )
        
        self.bars.append(minute_bar)
        self.latest_bar = minute_bar
        self._bar_data_received.set()
        
    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Handle end of historical data"""
        logger.info(f"Historical data completed. Received {len(self.bars)} bars")
        self._historical_data_end.set()
        
    def realtimeBar(self, reqId: int, time: int, open_: float, high: float, low: float, 
                    close: float, volume: int, wap: float, count: int):
        """Handle real-time 5-second bars (we'll aggregate to 1-minute)"""
        bar_time = datetime.fromtimestamp(time)
        logger.debug(f"Realtime Bar [{bar_time.strftime('%H:%M:%S')}] C:{close:.2f} V:{volume}")
        
        minute_bar = MinuteBar(
            timestamp=bar_time,
            open=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
            wap=wap,
            count=count
        )
        
        self._streaming_bars.append(minute_bar)
        self.latest_bar = minute_bar
        
        # Update EMA with the latest close price
        self.calculate_ema([close])
        
    def request_historical_bars(self, symbol: str, duration: str = "1 D", 
                               bar_size: str = "1 min") -> List[MinuteBar]:
        """Request historical minute bars for the current day"""
        self.bars.clear()
        self._bar_data_received.clear()
        self._historical_data_end.clear()
        
        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Request historical data
        req_id = self.get_next_request_id()
        end_time = ""  # Empty string means "now"
        use_rth = 1  # Regular trading hours only
        
        logger.info(f"Requesting historical bars for {symbol}: {duration} of {bar_size} bars")
        
        self.reqHistoricalData(
            reqId=req_id,
            contract=contract,
            endDateTime=end_time,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow="TRADES",
            useRTH=use_rth,
            formatDate=1,  # 1 = yyyyMMdd HH:mm:ss
            keepUpToDate=False,
            chartOptions=[]
        )
        
        # Wait for data
        if self._historical_data_end.wait(timeout=10):
            logger.info(f"Received {len(self.bars)} historical bars")
            # Calculate initial EMA if we have enough data
            if len(self.bars) >= self.ema_period:
                self.calculate_initial_ema()
            return self.bars
        else:
            logger.error("Timeout waiting for historical bar data")
            return []
            
    def start_streaming_bars(self, symbol: str):
        """Start streaming real-time 5-second bars"""
        if self.is_streaming:
            logger.warning("Already streaming bars")
            return
            
        # Create contract
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        
        # Request real-time bars (5-second bars)
        req_id = self.get_next_request_id()
        
        logger.info(f"Starting real-time bar streaming for {symbol}")
        
        self.reqRealTimeBars(
            reqId=req_id,
            contract=contract,
            barSize=5,  # 5-second bars
            whatToShow="TRADES",
            useRTH=False,
            realTimeBarsOptions=[]
        )
        
        self.is_streaming = True
        
    def stop_streaming_bars(self, req_id: int = None):
        """Stop streaming real-time bars"""
        if not self.is_streaming:
            return
            
        if req_id is not None:
            self.cancelRealTimeBars(req_id)
            
        self.is_streaming = False
        logger.info("Stopped real-time bar streaming")
        
    def calculate_initial_ema(self):
        """Calculate initial EMA from historical bars using SMA for the first value"""
        if len(self.bars) < self.ema_period:
            logger.warning(f"Not enough bars ({len(self.bars)}) to calculate {self.ema_period}-period EMA")
            return
            
        # Use Simple Moving Average for the first EMA value
        first_sma = sum(bar.close for bar in self.bars[:self.ema_period]) / self.ema_period
        self.ema_values = [first_sma]
        
        # Calculate EMA for remaining bars
        multiplier = 2 / (self.ema_period + 1)
        
        for i in range(self.ema_period, len(self.bars)):
            close_price = self.bars[i].close
            ema = (close_price * multiplier) + (self.ema_values[-1] * (1 - multiplier))
            self.ema_values.append(ema)
            
        self.current_ema = self.ema_values[-1] if self.ema_values else None
        
        logger.info(f"Calculated initial EMA({self.ema_period}): {self.current_ema:.2f}")
        
    def calculate_ema(self, new_prices: List[float]):
        """Calculate EMA for new price data"""
        if not new_prices:
            return
            
        # If no previous EMA, need to initialize
        if self.current_ema is None:
            if len(self.bars) >= self.ema_period:
                self.calculate_initial_ema()
            else:
                logger.debug("Not enough data to calculate EMA yet")
                return
                
        # Calculate EMA for each new price
        multiplier = 2 / (self.ema_period + 1)
        
        for price in new_prices:
            if self.current_ema is not None:
                self.current_ema = (price * multiplier) + (self.current_ema * (1 - multiplier))
                self.ema_values.append(self.current_ema)
                logger.debug(f"Updated EMA({self.ema_period}): {self.current_ema:.2f}")
                
    def get_current_ema(self) -> Optional[float]:
        """Get the current EMA value"""
        return self.current_ema
        
    def get_latest_bar(self) -> Optional[MinuteBar]:
        """Get the most recent bar"""
        return self.latest_bar
        
    def get_bars_for_period(self, minutes: int) -> List[MinuteBar]:
        """Get bars for the last N minutes"""
        if not self.bars:
            return []
            
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [bar for bar in self.bars if bar.timestamp >= cutoff_time]
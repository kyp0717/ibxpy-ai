"""
Stock Quote Module - Handles retrieving real-time stock quotes from TWS
"""

import logging
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

try:
    from ibapi.contract import Contract
    from ibapi.common import TickerId
    from ibapi.ticktype import TickTypeEnum
except ImportError:
    raise ImportError(
        "ibapi package not found. Please install it using the install_ibapi.sh script"
    )

from connection import TWSConnection

logger = logging.getLogger(__name__)


@dataclass
class StockQuote:
    """Data class for stock quote information"""
    symbol: str
    bid_price: float = 0.0
    ask_price: float = 0.0
    last_price: float = 0.0
    bid_size: int = 0
    ask_size: int = 0
    last_size: int = 0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def is_valid(self) -> bool:
        """Check if quote has valid price data"""
        return self.last_price > 0 or self.bid_price > 0 or self.ask_price > 0
    
    def __str__(self) -> str:
        """String representation of the quote"""
        return (f"{self.symbol}: Last=${self.last_price:.2f} "
                f"Bid=${self.bid_price:.2f} Ask=${self.ask_price:.2f} "
                f"Volume={self.volume:,}")


class QuoteClient(TWSConnection):
    """Extended TWS client for retrieving stock quotes"""
    
    def __init__(self):
        super().__init__()
        self.quotes: Dict[int, StockQuote] = {}
        self.req_id_to_symbol: Dict[int, str] = {}
        self._quote_received = threading.Event()
        self._current_req_id = 0
        
    def tickPrice(self, reqId: TickerId, tickType: int, price: float, attrib):
        """Handle price tick data from TWS"""
        if reqId not in self.quotes:
            symbol = self.req_id_to_symbol.get(reqId, "UNKNOWN")
            self.quotes[reqId] = StockQuote(symbol=symbol)
            
        quote = self.quotes[reqId]
        
        if tickType == TickTypeEnum.BID:
            quote.bid_price = price
            logger.debug(f"Bid price for {quote.symbol}: ${price}")
        elif tickType == TickTypeEnum.ASK:
            quote.ask_price = price
            logger.debug(f"Ask price for {quote.symbol}: ${price}")
        elif tickType == TickTypeEnum.LAST:
            quote.last_price = price
            logger.debug(f"Last price for {quote.symbol}: ${price}")
        elif tickType == TickTypeEnum.HIGH:
            quote.high = price
        elif tickType == TickTypeEnum.LOW:
            quote.low = price
        elif tickType == TickTypeEnum.CLOSE:
            quote.close = price
            
        self._quote_received.set()
        
    def tickSize(self, reqId: TickerId, tickType: int, size: int):
        """Handle size tick data from TWS"""
        if reqId not in self.quotes:
            symbol = self.req_id_to_symbol.get(reqId, "UNKNOWN")
            self.quotes[reqId] = StockQuote(symbol=symbol)
            
        quote = self.quotes[reqId]
        
        if tickType == TickTypeEnum.BID_SIZE:
            quote.bid_size = size
        elif tickType == TickTypeEnum.ASK_SIZE:
            quote.ask_size = size
        elif tickType == TickTypeEnum.LAST_SIZE:
            quote.last_size = size
        elif tickType == TickTypeEnum.VOLUME:
            quote.volume = size
            
    def tickString(self, reqId: TickerId, tickType: int, value: str):
        """Handle string tick data from TWS"""
        logger.debug(f"Tick string - ReqId: {reqId}, Type: {tickType}, Value: {value}")
        
    def tickGeneric(self, reqId: TickerId, tickType: int, value: float):
        """Handle generic tick data from TWS"""
        logger.debug(f"Tick generic - ReqId: {reqId}, Type: {tickType}, Value: {value}")
        
    def get_stock_quote(self, symbol: str, timeout: float = 5.0) -> Optional[StockQuote]:
        """
        Get real-time quote for a stock symbol
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            timeout: Maximum time to wait for quote data
            
        Returns:
            StockQuote object if successful, None otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to TWS")
            return None
            
        try:
            # Create contract for the stock
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Generate unique request ID
            req_id = self._get_next_req_id()
            self.req_id_to_symbol[req_id] = symbol
            
            # Clear event and initialize quote
            self._quote_received.clear()
            self.quotes[req_id] = StockQuote(symbol=symbol)
            
            logger.info(f"Requesting market data for {symbol}")
            
            # Request market data
            # Using snapshot=False for streaming data, genericTickList="" for all available ticks
            self.reqMktData(req_id, contract, "", False, False, [])
            
            # Wait for quote data
            start_time = time.time()
            while time.time() - start_time < timeout:
                if self._quote_received.wait(timeout=0.1):
                    quote = self.quotes[req_id]
                    if quote.is_valid():
                        # Cancel market data subscription
                        self.cancelMktData(req_id)
                        logger.info(f"Received quote for {symbol}: {quote}")
                        return quote
                        
            # Timeout - cancel subscription
            self.cancelMktData(req_id)
            
            # Return partial quote if we have any data
            quote = self.quotes.get(req_id)
            if quote and (quote.bid_price > 0 or quote.ask_price > 0):
                logger.warning(f"Partial quote received for {symbol}: {quote}")
                return quote
            else:
                logger.warning(f"No quote data received for {symbol} within timeout")
                return None
                
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None
            
    def _get_next_req_id(self) -> int:
        """Generate next request ID"""
        self._current_req_id += 1
        return self._current_req_id
        

def get_stock_quote(symbol: str, connection: Optional[TWSConnection] = None) -> Optional[StockQuote]:
    """
    Convenience function to get a stock quote
    
    Args:
        symbol: Stock symbol
        connection: Existing connection to use (optional)
        
    Returns:
        StockQuote object if successful, None otherwise
    """
    own_connection = False
    
    try:
        if connection is None:
            # Create our own connection
            logger.info("Creating new connection for quote request")
            quote_client = QuoteClient()
            if not quote_client.connect_to_tws():
                logger.error("Failed to connect to TWS")
                return None
            own_connection = True
        else:
            # Use existing connection (must be QuoteClient instance)
            if not isinstance(connection, QuoteClient):
                logger.error("Connection must be a QuoteClient instance")
                return None
            quote_client = connection
            
        # Get the quote
        return quote_client.get_stock_quote(symbol)
        
    finally:
        # Clean up if we created our own connection
        if own_connection and quote_client:
            quote_client.disconnect_from_tws()
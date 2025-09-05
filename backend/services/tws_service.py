"""TWS (Trader Workstation) service for Interactive Brokers integration.

This service provides a wrapper around the IBAPI to handle:
- Connection management
- Order execution
- Market data streaming
- Position tracking
"""
import asyncio
import threading
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from enum import Enum
import logging

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.common import TickerId, OrderId

from ..core.config import settings
from ..core.exceptions import TradingException
from ..core.error_handler import error_handler, with_retry, RetryPolicy, ErrorSeverity
from .order_manager import order_manager
from .state_manager import state_manager
from .connection_recovery import connection_recovery

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """TWS connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class TWSWrapper(EWrapper):
    """Implements IB API wrapper callbacks."""
    
    def __init__(self):
        super().__init__()
        self.next_valid_id = None
        self.connection_event = threading.Event()
        
    def nextValidId(self, orderId: int):
        """Receives next valid order ID from TWS."""
        super().nextValidId(orderId)
        self.next_valid_id = orderId
        logger.info(f"Next valid order ID: {orderId}")
        self.connection_event.set()
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handles errors from TWS."""
        logger.error(f"Error {errorCode}: {errorString} (reqId: {reqId})")
        
        # Determine severity based on error code
        if errorCode >= 1000:  # System errors
            severity = ErrorSeverity.CRITICAL
        elif errorCode >= 500:  # Connection errors
            severity = ErrorSeverity.HIGH
        elif errorCode >= 200:  # Order errors
            severity = ErrorSeverity.MEDIUM
        else:
            severity = ErrorSeverity.LOW
            
        # Record error
        error_handler.record_error(
            error_type=f"TWS_ERROR_{errorCode}",
            message=errorString,
            severity=severity,
            context={"reqId": reqId, "errorCode": errorCode}
        )
        
        if errorCode == 502:  # Cannot connect to TWS
            self.connection_event.set()
            
    def contractDetails(self, reqId: int, contractDetails):
        """Receives contract details."""
        logger.debug(f"Contract details for reqId {reqId}: {contractDetails}")
        
    def orderStatus(self, orderId: OrderId, status: str, filled: float,
                   remaining: float, avgFillPrice: float, permId: int,
                   parentId: int, lastFillPrice: float, clientId: int,
                   whyHeld: str, mktCapPrice: float):
        """Receives order status updates."""
        logger.info(f"Order {orderId} status: {status}, filled: {filled}, remaining: {remaining}")
        
        # Update order manager asynchronously
        asyncio.create_task(
            order_manager.update_order_status(
                order_id=orderId,
                status=status,
                filled=int(filled),
                remaining=int(remaining),
                avg_fill_price=avgFillPrice,
                last_fill_price=lastFillPrice,
                message=whyHeld if whyHeld else ""
            )
        )
        
    def openOrder(self, orderId: OrderId, contract: Contract, order: Order,
                  orderState):
        """Receives open order details."""
        logger.info(f"Open order {orderId}: {contract.symbol} {order.action} {order.totalQuantity}")
        
    def execDetails(self, reqId: int, contract: Contract, execution):
        """Receives execution details."""
        logger.info(f"Execution: {contract.symbol} {execution.shares}@{execution.price}")
        
        # Update order manager with execution details
        asyncio.create_task(
            order_manager.add_execution(
                order_id=execution.orderId,
                exec_id=execution.execId,
                symbol=contract.symbol,
                side=execution.side,
                quantity=int(execution.shares),
                price=execution.price,
                commission=execution.commission if hasattr(execution, 'commission') else 0.0,
                cumulative_quantity=int(execution.cumQty),
                average_price=execution.avgPrice
            )
        )
        
    def position(self, account: str, contract: Contract, position: float,
                avgCost: float):
        """Receives position updates."""
        logger.info(f"Position: {account} {contract.symbol} {position}@{avgCost}")
        
        # Update state manager with position
        asyncio.create_task(
            state_manager.update_position(
                symbol=contract.symbol,
                quantity=position,
                avg_cost=avgCost,
                current_price=avgCost,  # Will be updated with market data
                account=account
            )
        )
        
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,
                      currency: str):
        """Receives account summary."""
        logger.debug(f"Account {account} {tag}: {value} {currency}")
        
    def realtimeBar(self, reqId: TickerId, time: int, open_: float, high: float, 
                   low: float, close: float, volume: int, wap: float, count: int):
        """Receives real-time 5-second bars."""
        logger.debug(f"Bar: {datetime.fromtimestamp(time)} O:{open_} H:{high} L:{low} C:{close} V:{volume}")


class TWSClient(EClient):
    """Implements IB API client with async support."""
    
    def __init__(self, wrapper):
        super().__init__(wrapper)
        

class TWSService:
    """Service for managing TWS connection and operations."""
    
    def __init__(self):
        self.wrapper = TWSWrapper()
        self.client = TWSClient(self.wrapper)
        self.connection_state = ConnectionState.DISCONNECTED
        self._api_thread: Optional[threading.Thread] = None
        self._market_data_callbacks: Dict[int, Callable] = {}
        self._order_callbacks: Dict[int, Callable] = {}
        self._req_id_counter = 1000
        
        # Set reference for recovery service
        connection_recovery.set_tws_service(self)
        
    @with_retry(RetryPolicy(max_attempts=3, initial_delay=2.0))
    async def connect(self, 
                     host: Optional[str] = None,
                     port: Optional[int] = None,
                     client_id: Optional[int] = None) -> bool:
        """Connect to TWS/IB Gateway with retry logic.
        
        Args:
            host: TWS host (default from settings)
            port: TWS port (default from settings)
            client_id: Client ID (default from settings)
            
        Returns:
            True if connection successful
        """
        if self.connection_state == ConnectionState.CONNECTED:
            logger.warning("Already connected to TWS")
            return True
            
        host = host or settings.tws_host
        port = port or settings.tws_port
        client_id = client_id or settings.tws_client_id
        
        logger.info(f"Connecting to TWS at {host}:{port} with client ID {client_id}")
        self.connection_state = ConnectionState.CONNECTING
        
        circuit_breaker = error_handler.get_circuit_breaker("tws_connection")
        
        try:
            # Use circuit breaker for connection
            async def _connect():
                # Connect in sync mode
                self.client.connect(host, port, client_id)
                
                # Start API thread
                self._api_thread = threading.Thread(target=self._run_api_thread, daemon=True)
                self._api_thread.start()
                
                # Wait for connection confirmation
                if self.wrapper.connection_event.wait(timeout=5):
                    if self.wrapper.next_valid_id is not None:
                        self.connection_state = ConnectionState.CONNECTED
                        logger.info(f"Connected to TWS. Next valid ID: {self.wrapper.next_valid_id}")
                        return True
                    else:
                        raise TradingException("No valid order ID received")
                else:
                    raise TradingException("Connection timeout")
                    
            result = await circuit_breaker.call_async(_connect)
            return result
                
        except Exception as e:
            self.connection_state = ConnectionState.ERROR
            error_handler.record_error(
                error_type="TWS_CONNECTION_FAILED",
                message=str(e),
                severity=ErrorSeverity.CRITICAL,
                context={"host": host, "port": port, "client_id": client_id}
            )
            logger.error(f"Connection error: {e}")
            return False
            
    def _run_api_thread(self):
        """Run the API message processing thread."""
        try:
            self.client.run()
        except Exception as e:
            logger.error(f"API thread error: {e}")
            self.connection_state = ConnectionState.ERROR
            
    async def disconnect(self):
        """Disconnect from TWS."""
        if self.connection_state != ConnectionState.CONNECTED:
            return
            
        logger.info("Disconnecting from TWS")
        self.client.disconnect()
        self.connection_state = ConnectionState.DISCONNECTED
        
        # Wait for thread to finish
        if self._api_thread and self._api_thread.is_alive():
            self._api_thread.join(timeout=2)
            
    def _get_next_req_id(self) -> int:
        """Get next request ID."""
        self._req_id_counter += 1
        return self._req_id_counter
        
    async def place_order(self, contract: Contract, order: Order) -> int:
        """Place an order.
        
        Args:
            contract: IB Contract object
            order: IB Order object
            
        Returns:
            Order ID
        """
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        order_id = self.wrapper.next_valid_id
        self.wrapper.next_valid_id += 1
        
        logger.info(f"Placing order {order_id}: {contract.symbol} {order.action} {order.totalQuantity}")
        self.client.placeOrder(order_id, contract, order)
        
        return order_id
        
    async def cancel_order(self, order_id: int):
        """Cancel an order.
        
        Args:
            order_id: Order ID to cancel
        """
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        logger.info(f"Cancelling order {order_id}")
        self.client.cancelOrder(order_id, "")
        
    async def request_market_data(self, contract: Contract, callback: Callable) -> int:
        """Request real-time market data.
        
        Args:
            contract: IB Contract object
            callback: Function to call with market data updates
            
        Returns:
            Request ID
        """
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        req_id = self._get_next_req_id()
        self._market_data_callbacks[req_id] = callback
        
        logger.info(f"Requesting market data for {contract.symbol} (reqId: {req_id})")
        self.client.reqMktData(req_id, contract, "", False, False, [])
        
        return req_id
        
    async def cancel_market_data(self, req_id: int):
        """Cancel market data subscription.
        
        Args:
            req_id: Request ID to cancel
        """
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        logger.info(f"Cancelling market data subscription {req_id}")
        self.client.cancelMktData(req_id)
        
        if req_id in self._market_data_callbacks:
            del self._market_data_callbacks[req_id]
            
    async def request_realtime_bars(self, contract: Contract, callback: Callable) -> int:
        """Request real-time 5-second bars.
        
        Args:
            contract: IB Contract object
            callback: Function to call with bar updates
            
        Returns:
            Request ID
        """
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        req_id = self._get_next_req_id()
        self._market_data_callbacks[req_id] = callback
        
        logger.info(f"Requesting real-time bars for {contract.symbol} (reqId: {req_id})")
        self.client.reqRealTimeBars(req_id, contract, 5, "TRADES", False, [])
        
        return req_id
        
    async def request_positions(self):
        """Request all positions."""
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        logger.info("Requesting positions")
        self.client.reqPositions()
        
    async def request_account_summary(self):
        """Request account summary."""
        if self.connection_state != ConnectionState.CONNECTED:
            raise TradingException("Not connected to TWS")
            
        req_id = self._get_next_req_id()
        logger.info(f"Requesting account summary (reqId: {req_id})")
        self.client.reqAccountSummary(req_id, "All", "$LEDGER:ALL")
        
    def create_stock_contract(self, symbol: str, exchange: str = "SMART") -> Contract:
        """Create a stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default SMART)
            
        Returns:
            IB Contract object
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = exchange
        contract.currency = "USD"
        return contract
        
    def create_market_order(self, action: str, quantity: int) -> Order:
        """Create a market order.
        
        Args:
            action: BUY or SELL
            quantity: Number of shares
            
        Returns:
            IB Order object
        """
        order = Order()
        order.action = action
        order.orderType = "MKT"
        order.totalQuantity = quantity
        order.tif = "GTC"  # Good till cancelled
        return order
        
    def create_limit_order(self, action: str, quantity: int, limit_price: float) -> Order:
        """Create a limit order.
        
        Args:
            action: BUY or SELL
            quantity: Number of shares
            limit_price: Limit price
            
        Returns:
            IB Order object
        """
        order = Order()
        order.action = action
        order.orderType = "LMT"
        order.totalQuantity = quantity
        order.lmtPrice = limit_price
        order.tif = "GTC"
        return order
        
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status information."""
        return {
            "state": self.connection_state.value,
            "connected": self.connection_state == ConnectionState.CONNECTED,
            "host": settings.tws_host,
            "port": settings.tws_port,
            "client_id": settings.tws_client_id,
            "next_order_id": self.wrapper.next_valid_id if self.wrapper.next_valid_id else None
        }


# Global TWS service instance
tws_service = TWSService()
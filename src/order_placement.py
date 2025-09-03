"""
Order Placement Module - Handles placing stock orders through TWS
"""

import logging
import threading
import time
import sys
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

try:
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.common import OrderId
    from ibapi.execution import Execution
    from ibapi.order_state import OrderState
except ImportError:
    raise ImportError(
        "ibapi package not found. Please install it using the install_ibapi.sh script"
    )

from connection import TWSConnection
from stock_quote import QuoteClient, StockQuote

logger = logging.getLogger(__name__)


@dataclass
class OrderResult:
    """Data class for order execution result"""
    order_id: int
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    order_type: str  # MKT, LMT, etc
    limit_price: float = 0.0
    status: str = "PENDING"
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def is_filled(self) -> bool:
        """Check if order is completely filled"""
        return self.status == "FILLED" or self.filled_qty >= self.quantity
    
    def __str__(self) -> str:
        """String representation of the order"""
        if self.order_type == "LMT":
            price_info = f"@${self.limit_price:.2f}"
        else:
            price_info = "@MARKET"
        
        status_info = f"Status: {self.status}"
        if self.filled_qty > 0:
            status_info += f" ({self.filled_qty}/{self.quantity} filled @${self.avg_fill_price:.2f})"
            
        return f"Order #{self.order_id}: {self.action} {self.quantity} {self.symbol} {price_info} - {status_info}"


class OrderClient(QuoteClient):
    """Extended client for placing orders"""
    
    def __init__(self):
        super().__init__()
        self.orders: Dict[int, OrderResult] = {}
        self._order_filled = threading.Event()
        self._order_status_received = threading.Event()
        self.positions: Dict[str, Dict[str, Any]] = {}  # Track positions for PnL
        self.actual_positions: Dict[str, Dict[str, Any]] = {}  # Actual positions from TWS
        self._positions_received = threading.Event()
        self.pnl: Dict[str, float] = {}  # Track PnL by symbol
        
    def orderStatus(self, orderId: OrderId, status: str, filled: float, remaining: float,
                   avgFillPrice: float, permId: int, parentId: int, lastFillPrice: float,
                   clientId: int, whyHeld: str, mktCapPrice: float):
        """Handle order status updates"""
        logger.info(f"Order #{orderId} - Status: {status}, Filled: {filled}, Remaining: {remaining}, AvgPrice: ${avgFillPrice}")
        
        if orderId in self.orders:
            order_result = self.orders[orderId]
            order_result.status = status
            order_result.filled_qty = int(filled)
            order_result.avg_fill_price = avgFillPrice
            
            if status in ["Filled", "FILLED"]:
                order_result.status = "FILLED"
                self._order_filled.set()
                # Track position for PnL
                if order_result.action == "BUY":
                    self.positions[order_result.symbol] = {
                        "quantity": order_result.filled_qty,
                        "avg_cost": avgFillPrice,
                        "total_cost": order_result.filled_qty * avgFillPrice
                    }
            elif status in ["Cancelled", "CANCELLED"]:
                order_result.status = "CANCELLED"
                self._order_status_received.set()
            elif status in ["Submitted", "SUBMITTED", "PreSubmitted", "PRESUBMITTED"]:
                order_result.status = "SUBMITTED"
                self._order_status_received.set()
                
    def openOrder(self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState):
        """Handle open order messages"""
        logger.info(f"Open order #{orderId}: {order.action} {order.totalQuantity} {contract.symbol} - Status: {orderState.status}")
        
    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        """Handle execution details"""
        logger.info(f"Execution: {execution.orderId} - {execution.shares} shares @ ${execution.price}")
        
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """Handle position updates from TWS"""
        logger.info(f"Position: {contract.symbol} - {position} shares @ avg cost ${avgCost}")
        self.actual_positions[contract.symbol] = {
            "account": account,
            "position": position,
            "avg_cost": avgCost
        }
        
    def positionEnd(self):
        """Called when all positions have been received"""
        logger.info("All positions received")
        self._positions_received.set()
        
    def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
        """Handle PnL updates"""
        logger.info(f"PnL: Daily=${dailyPnL}, Unrealized=${unrealizedPnL}, Realized=${realizedPnL}")
        
    def pnlSingle(self, reqId: int, pos: int, dailyPnL: float, unrealizedPnL: float, 
                  realizedPnL: float, value: float):
        """Handle single position PnL updates"""
        logger.info(f"Position PnL: Pos={pos}, Unrealized=${unrealizedPnL}, Realized=${realizedPnL}")
        
    def request_positions(self):
        """Request all positions from TWS"""
        self._positions_received.clear()
        self.actual_positions.clear()
        logger.info("Requesting positions from TWS...")
        self.reqPositions()
        
        # Wait for positions
        if self._positions_received.wait(timeout=5):
            logger.info(f"Received {len(self.actual_positions)} positions")
            return self.actual_positions
        else:
            logger.warning("Timeout waiting for positions")
            return {}
        
    def place_market_order(self, symbol: str, action: str, quantity: int) -> Optional[OrderResult]:
        """
        Place a market order
        
        Args:
            symbol: Stock symbol
            action: "BUY" or "SELL"
            quantity: Number of shares
            
        Returns:
            OrderResult if successful, None otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to TWS")
            return None
            
        try:
            # Create contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create market order
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = "MKT"
            order.eTradeOnly = False
            order.firmQuoteOnly = False
            
            # Get order ID
            order_id = self.next_order_id or 1
            self.next_order_id = order_id + 1
            
            # Create order result
            result = OrderResult(
                order_id=order_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type="MKT"
            )
            self.orders[order_id] = result
            
            # Clear events
            self._order_filled.clear()
            self._order_status_received.clear()
            
            logger.info(f"Placing market order: {action} {quantity} {symbol}")
            
            # Place the order
            self.placeOrder(order_id, contract, order)
            
            # Wait for order status
            if self._order_status_received.wait(timeout=5):
                logger.info(f"Order #{order_id} submitted successfully")
                return result
            else:
                logger.warning(f"Order #{order_id} status not received within timeout")
                return result
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
            
    def place_limit_order(self, symbol: str, action: str, quantity: int, limit_price: float) -> Optional[OrderResult]:
        """
        Place a limit order
        
        Args:
            symbol: Stock symbol
            action: "BUY" or "SELL"
            quantity: Number of shares
            limit_price: Limit price
            
        Returns:
            OrderResult if successful, None otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to TWS")
            return None
            
        try:
            # Create contract
            contract = Contract()
            contract.symbol = symbol
            contract.secType = "STK"
            contract.exchange = "SMART"
            contract.currency = "USD"
            
            # Create limit order
            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = "LMT"
            order.lmtPrice = limit_price
            order.eTradeOnly = False
            order.firmQuoteOnly = False
            
            # Get order ID
            order_id = self.next_order_id or 1
            self.next_order_id = order_id + 1
            
            # Create order result
            result = OrderResult(
                order_id=order_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type="LMT",
                limit_price=limit_price
            )
            self.orders[order_id] = result
            
            # Clear events
            self._order_filled.clear()
            self._order_status_received.clear()
            
            logger.info(f"Placing limit order: {action} {quantity} {symbol} @ ${limit_price}")
            
            # Place the order
            self.placeOrder(order_id, contract, order)
            
            # Wait for order status
            if self._order_status_received.wait(timeout=5):
                logger.info(f"Order #{order_id} submitted successfully")
                return result
            else:
                logger.warning(f"Order #{order_id} status not received within timeout")
                return result
                
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def interactive_order_prompt(symbol: str, client: OrderClient, quantity: int = 100, 
                            order_type: str = "MKT", test_mode: bool = False) -> Optional[OrderResult]:
    """
    Interactive prompt for placing an order with real-time price updates
    
    Args:
        symbol: Stock symbol
        client: Connected OrderClient
        quantity: Number of shares to buy
        order_type: Order type (MKT or LMT)
        test_mode: If True, simulate user input for testing
        
    Returns:
        OrderResult if order placed, None if cancelled
    """
    if not client.is_connected():
        print("Error: Not connected to TWS")
        return None
        
    try:
        while True:
            # Get current quote
            quote = client.get_stock_quote(symbol, timeout=3)
            
            if not quote or not quote.is_valid():
                print(f"Failed to get quote for {symbol}")
                return None
                
            # Clear screen and display current price
            if not test_mode:
                clear_screen()
                
            print("\n" + "="*50)
            print(f"  {symbol}: ${quote.last_price:.2f}")
            print(f"  Bid: ${quote.bid_price:.2f} | Ask: ${quote.ask_price:.2f}")
            print(f"  Volume: {quote.volume:,}")
            print("="*50)
            print(f"\nOrder: BUY {quantity} shares at MARKET price")
            print(f"Estimated cost: ${quote.ask_price * quantity:,.2f}")
            print("\nOpen trade (y/n)? ", end='', flush=True)
            
            if test_mode:
                # In test mode, automatically select 'y'
                user_input = 'y'
                print(user_input)
            else:
                # Wait for user input with timeout
                import select
                
                # Check if input is available within 5 seconds
                if sys.stdin in select.select([sys.stdin], [], [], 5)[0]:
                    user_input = sys.stdin.readline().strip().lower()
                else:
                    # No input received, refresh the quote
                    continue
                    
            if user_input == 'y':
                print(f"\nPlacing order to BUY {quantity} shares of {symbol}...")
                
                if order_type == "MKT":
                    result = client.place_market_order(symbol, "BUY", quantity)
                else:
                    # For limit orders, use the ask price
                    result = client.place_limit_order(symbol, "BUY", quantity, quote.ask_price)
                    
                if result:
                    print(f"✓ Order placed successfully!")
                    print(f"  {result}")
                    
                    # Wait a moment for order to fill (for market orders)
                    if order_type == "MKT":
                        time.sleep(2)
                        if result.order_id in client.orders:
                            updated_result = client.orders[result.order_id]
                            print(f"\nOrder status: {updated_result}")
                else:
                    print("✗ Failed to place order")
                    
                return result
                
            elif user_input == 'n':
                print("\nRefreshing quote...")
                time.sleep(1)
                continue
                
            else:
                print("Invalid input. Please enter 'y' or 'n'")
                if not test_mode:
                    time.sleep(1)
                    
    except KeyboardInterrupt:
        print("\n\nOrder cancelled by user")
        return None
    except Exception as e:
        print(f"\nError during order placement: {e}")
        return None


def place_order_with_prompt(symbol: str, quantity: int = 100, 
                           host: str = "127.0.0.1", port: int = 7500, 
                           client_id: int = 20, test_mode: bool = False) -> Optional[OrderResult]:
    """
    Convenience function to place an order with interactive prompt
    
    Args:
        symbol: Stock symbol
        quantity: Number of shares
        host: TWS host
        port: TWS port
        client_id: Client ID
        test_mode: If True, simulate user input for testing
        
    Returns:
        OrderResult if successful, None otherwise
    """
    client = None
    
    try:
        # Create and connect client
        print("Connecting to TWS...")
        client = OrderClient()
        
        if not client.connect_to_tws(host, port, client_id):
            print("Failed to connect to TWS")
            return None
            
        print("Connected successfully!")
        
        # Run interactive prompt
        result = interactive_order_prompt(symbol, client, quantity, test_mode=test_mode)
        
        return result
        
    finally:
        # Disconnect
        if client and client.is_connected():
            client.disconnect_from_tws()
            print("\nDisconnected from TWS")
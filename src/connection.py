"""
TWS Connection Module - Handles connection to Interactive Brokers TWS
"""

import logging
import threading
import time
from typing import Optional

try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.contract import Contract
    from ibapi.common import TickerId
except ImportError:
    raise ImportError(
        "ibapi package not found. Please install it using the install_ibapi.sh script "
        "or follow instructions in IBAPI_INSTALLATION.md"
    )

logger = logging.getLogger(__name__)


class TWSConnection(EWrapper, EClient):
    """
    Main TWS connection class that handles communication with Interactive Brokers
    """
    
    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.connected = False
        self.next_order_id = None
        self.connection_time = None
        self._thread = None
        
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle error messages from TWS"""
        if errorCode == 502:
            logger.warning(f"Cannot connect to TWS: {errorString}")
        elif errorCode == 504:
            logger.info("Connected to TWS but not logged in")
        elif errorCode >= 2000:
            logger.info(f"TWS Info: {errorString}")
        else:
            logger.error(f"Error {errorCode}: {errorString}")
            
    def connectAck(self):
        """Called when connection is acknowledged"""
        logger.info("Connection acknowledged by TWS")
        self.connected = True
        
    def connectionClosed(self):
        """Called when connection is closed"""
        logger.info("Connection to TWS closed")
        self.connected = False
        
    def nextValidId(self, orderId: int):
        """Receives next valid order ID"""
        logger.info(f"Next valid order ID: {orderId}")
        self.next_order_id = orderId
        self.connection_time = time.time()
        
    def connect_to_tws(self, host: str = "127.0.0.1", port: int = 7500, client_id: int = 1) -> bool:
        """
        Connect to TWS or IB Gateway
        
        Args:
            host: TWS host address (default: localhost)
            port: TWS port (default: 7500)
            client_id: Unique client identifier
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Attempting to connect to TWS at {host}:{port} with client ID {client_id}")
            
            # Connect to TWS
            self.connect(host, port, client_id)
            
            # Start the message processing thread
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
            
            # Wait for connection to establish (max 5 seconds)
            timeout = 5
            start_time = time.time()
            
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
                
            if self.connected:
                logger.info(f"Successfully connected to TWS at {host}:{port}")
                
                # Wait for nextValidId to be received
                while self.next_order_id is None and (time.time() - start_time) < timeout:
                    time.sleep(0.1)
                    
                if self.next_order_id is not None:
                    logger.info("Connection fully established and ready")
                    return True
                else:
                    logger.warning("Connected but did not receive next order ID")
                    return True
            else:
                logger.error(f"Failed to connect to TWS at {host}:{port}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to TWS: {e}")
            return False
            
    def disconnect_from_tws(self):
        """Disconnect from TWS"""
        if self.isConnected():
            logger.info("Disconnecting from TWS...")
            self.disconnect()
            
            # Wait for thread to finish
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
                
            logger.info("Disconnected from TWS")
        else:
            logger.info("Not connected to TWS")
            
    def is_connected(self) -> bool:
        """Check if connected to TWS"""
        return self.connected and self.isConnected()


def create_connection(host: str = "127.0.0.1", port: int = 7500, client_id: int = 1) -> Optional[TWSConnection]:
    """
    Factory function to create and establish TWS connection
    
    Args:
        host: TWS host address
        port: TWS port  
        client_id: Unique client identifier
        
    Returns:
        TWSConnection object if successful, None otherwise
    """
    connection = TWSConnection()
    
    if connection.connect_to_tws(host, port, client_id):
        return connection
    else:
        return None
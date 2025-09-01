#!/usr/bin/env python
"""
Main entry point for the IBXPy AI Trading Application
"""

import sys
import logging
import time
from pathlib import Path

from connection import create_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Main application entry point"""
    logger.info("Starting IBXPy AI Trading Application")
    
    try:
        print("IBXPy AI Trading Application")
        print("=" * 40)
        
        # Create connection to TWS
        print("Connecting to TWS on port 7500...")
        connection = create_connection(host="127.0.0.1", port=7500, client_id=1)
        
        if connection:
            print("✅ Successfully connected to TWS!")
            print(f"Next Order ID: {connection.next_order_id}")
            
            # Keep connection alive for demonstration
            print("\nConnection established. Press Ctrl+C to exit.")
            try:
                while connection.is_connected():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
                
            # Disconnect gracefully
            connection.disconnect_from_tws()
        else:
            print("❌ Failed to connect to TWS")
            print("Please ensure TWS is running and API connections are enabled")
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"Import error: {e}")
        print("\n❌ ibapi package not found!")
        print("Please run ./install_ibapi.sh to install the IB API")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
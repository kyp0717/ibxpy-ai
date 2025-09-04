#!/usr/bin/env python
"""
Main entry point for the IBXPy AI Trading Application
Phase 11 - Command-line Arguments for Symbol and Position Size
"""

import sys
import argparse
import logging
import time
import os
import select
from pathlib import Path
from datetime import datetime

from order_placement import OrderClient

logging.basicConfig(
    level=logging.WARNING,  # Reduced to show only important messages
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def clear_screen():
    """Clear the terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def display_menu(symbol, position_size):
    """Display the simplified main menu with symbol and position info"""
    print("\n" + "=" * 50)
    print("       IBX Trading App ")
    print("=" * 50)
    print(f"1. Begin trading {symbol} with size {position_size}")
    print("2. Exit")
    print("=" * 50)
    print("Enter your choice (1-2): ", end="", flush=True)


def calculate_pnl(position, current_price):
    """Calculate PnL for a position"""
    if not position:
        return 0

    current_value = position["quantity"] * current_price
    total_cost = position["total_cost"]
    return current_value - total_cost


def format_order_status(
    symbol, status, filled_qty=0, total_qty=0, price=0, order_type="Open"
):
    """Format order status for display with order type (Open/Close)"""
    if status == "FILLED":
        return f"**{symbol}** [TWS {order_type} Order Status] Filled at ${price:.2f}"
    elif filled_qty > 0 and filled_qty < total_qty:
        return f"**{symbol}** [TWS {order_type} Order Status] Partially Filled {filled_qty}/{total_qty}"
    else:
        return f"**{symbol}** [TWS {order_type} Order Status] {status}"


def format_pnl_display(symbol, pnl):
    """Format PnL display with GAIN/LOSS indicator"""
    abs_pnl = abs(pnl)

    if pnl < 0:
        # Red for negative PnL - LOSS
        color = "\033[91m"
        indicator = "LOSS"
    else:
        # Green for positive or zero PnL - GAIN
        color = "\033[92m"
        indicator = "GAIN"

    reset = "\033[0m"
    return f"{color}**{symbol}** [TWS PnL] ${abs_pnl:.2f} --- {indicator}{reset}"



def monitor_order_status(
    client: OrderClient, order_result, symbol: str, order_type="Open"
):
    """Monitor order status until it's filled with proper formatting"""
    print(f"\n{'=' * 50}")
    print(f"  Monitoring {order_type} Order #{order_result.order_id}")
    print(f"{'=' * 50}")

    last_status = ""

    while not order_result.is_filled():
        # Get updated order status
        if order_result.order_id in client.orders:
            order_result = client.orders[order_result.order_id]

        # Format and display status with order type
        status_msg = format_order_status(
            symbol,
            order_result.status,
            order_result.filled_qty,
            order_result.quantity,
            order_result.avg_fill_price,
            order_type,
        )

        if status_msg != last_status:
            print(f"\r{status_msg}", end="")
            print(" " * 20, end="", flush=True)  # Clear any remaining text
            last_status = status_msg

        if order_result.status == "CANCELLED":
            print(f"\n\n❌ Order cancelled")
            break
        elif order_result.is_filled():
            # Display final filled status
            final_msg = format_order_status(
                symbol,
                "FILLED",
                price=order_result.avg_fill_price,
                order_type=order_type,
            )
            print(f"\r{final_msg}")
            print(f"\n✅ {order_type} order completely filled!")
            print(
                f"   {order_result.quantity} shares @ ${order_result.avg_fill_price:.2f}"
            )
            print(
                f"   Total: ${order_result.quantity * order_result.avg_fill_price:,.2f}"
            )
            break

        # Small delay before checking again
        time.sleep(0.5)

    return order_result.is_filled()


def place_sell_order(client: OrderClient, symbol: str, quantity: int, price: float):
    """Place a sell order to close position"""
    print(
        f"\n\033[92mPlacing SELL order for {quantity} shares of {symbol} at ${price:.2f}...\033[0m"
    )

    # Place limit sell order
    result = client.place_limit_order(symbol, "SELL", quantity, price)

    if result:
        print(f"✅ Sell order placed successfully!")
        print(f"   Order ID: {result.order_id}")
        print(f"   Type: LIMIT SELL @ ${result.limit_price:.2f}")

        # Monitor until filled with "Close" order type
        filled = monitor_order_status(client, result, symbol, order_type="Close")
        if filled:
            # Store final PnL before clearing position
            if symbol in client.positions:
                position = client.positions[symbol]
                final_pnl = (result.avg_fill_price - position["avg_cost"]) * position[
                    "quantity"
                ]
                client.pnl[symbol] = final_pnl
                # Clear position from tracking
                del client.positions[symbol]
            return True, result
    else:
        print("❌ Failed to place sell order")

    return False, None


def perform_audit(client: OrderClient, symbol: str):
    """Perform audit to verify position is closed and show final PnL with commissions"""
    print(f"\n{'=' * 50}")
    print(f"  Performing Audit for {symbol}")
    print(f"{'=' * 50}")

    # Request actual positions from TWS
    actual_positions = client.request_positions()

    # Check position for symbol
    position_qty = 0
    if symbol in actual_positions:
        position_qty = actual_positions[symbol]["position"]

    # Get final PnL and commissions
    final_pnl = client.pnl.get(symbol, 0.0)
    
    # Get commission data
    total_commission = 0.0
    if symbol in client.commissions:
        total_commission = client.commissions[symbol]["total"]
    
    # Calculate PnL after commissions
    pnl_after_commission = final_pnl - total_commission

    # Display audit results
    print(f"\n**{symbol}** [TWS Audit] Final Position {position_qty}")
    print(f"**{symbol}** [TWS Audit] Commission Cost ${total_commission:.2f}")
    
    # Display raw PnL
    if final_pnl < 0:
        color = "\033[91m"  # Red
        indicator = "LOSS"
    else:
        color = "\033[92m"  # Green
        indicator = "GAIN"
    reset = "\033[0m"
    print(f"{color}**{symbol}** [TWS Audit] Final PnL ${abs(final_pnl):.2f} --- {indicator}{reset}")
    
    # Display PnL after commission
    if pnl_after_commission < 0:
        color = "\033[91m"  # Red
        indicator = "LOSS"
    else:
        color = "\033[92m"  # Green
        indicator = "GAIN"
    print(f"{color}**{symbol}** [TWS Audit] Final PnL - Commission ${abs(pnl_after_commission):.2f} --- {indicator}{reset}")

    if position_qty == 0:
        print(f"\n✅ Position successfully closed")
    else:
        print(f"\n⚠️  Warning: Position still open with {position_qty} shares")

    return position_qty == 0, pnl_after_commission


def begin_trading(client: OrderClient, symbol: str, position_size: int):
    """Begin trading - complete lifecycle from open to audit"""
    print(f"\nInitiating trading with {symbol} ...")
    print(f"Position size: {position_size} shares")
    time.sleep(2)

    order_placed = False
    order_filled = False
    filled_order = None
    position_closed = False
    close_order = None
    audit_complete = False

    try:
        while True:
            # Get current quote
            quote = client.get_stock_quote(symbol, timeout=2)

            if quote and quote.is_valid():
                # Clear and display quote
                clear_screen()
                print(f"\n{'=' * 50}")
                print(f"   Monitoring: {symbol}")
                print(f"{'=' * 50}")

                print(f"\n  Time: {quote.timestamp.strftime('%H:%M:%S')}")
                print(f"  Last Price: ${quote.last_price:.2f}")
                print(f"  Bid: ${quote.bid_price:.2f} x {quote.bid_size}")
                print(f"  Ask: ${quote.ask_price:.2f} x {quote.ask_size}")
                print(f"  Spread: ${(quote.ask_price - quote.bid_price):.2f}")
                print(f"  Volume: {quote.volume:,}")

                if quote.close > 0:
                    change = quote.last_price - quote.close
                    change_pct = (change / quote.close) * 100
                    symbol_str = "+" if change >= 0 else ""
                    color = "\033[92m" if change >= 0 else "\033[91m"
                    reset = "\033[0m"
                    print(
                        f"  Day Change: {color}{symbol_str}${change:.2f} ({symbol_str}{change_pct:.2f}%){reset}"
                    )

                # Display order statuses if they exist
                if order_filled and filled_order:
                    print(f"\n{'=' * 50}")
                    # Display open order status
                    open_msg = format_order_status(
                        symbol,
                        "FILLED",
                        price=filled_order.avg_fill_price,
                        order_type="Open",
                    )
                    print(f"  {open_msg}")

                    # Display PnL if position is open
                    if not position_closed and symbol in client.positions:
                        pnl = calculate_pnl(client.positions[symbol], quote.last_price)
                        pnl_display = format_pnl_display(symbol, pnl)
                        print(f"  {pnl_display}")

                    # Display close order status if exists
                    if position_closed and close_order:
                        close_msg = format_order_status(
                            symbol,
                            "FILLED",
                            price=close_order.avg_fill_price,
                            order_type="Close",
                        )
                        print(f"  {close_msg}")

                # Display audit results if complete
                if audit_complete and symbol in client.pnl:
                    print(f"\n{'=' * 50}")
                    
                    # Get commission data
                    total_commission = 0.0
                    if symbol in client.commissions:
                        total_commission = client.commissions[symbol]["total"]
                    
                    final_pnl = client.pnl[symbol]
                    pnl_after_commission = final_pnl - total_commission
                    
                    # Display all audit info
                    print(f"  **{symbol}** [TWS Audit] Final Position 0")
                    print(f"  **{symbol}** [TWS Audit] Commission Cost ${total_commission:.2f}")
                    
                    # Raw PnL
                    if final_pnl < 0:
                        color = "\033[91m"
                        indicator = "LOSS"
                    else:
                        color = "\033[92m"
                        indicator = "GAIN"
                    reset = "\033[0m"
                    print(f"  {color}**{symbol}** [TWS Audit] Final PnL ${abs(final_pnl):.2f} --- {indicator}{reset}")
                    
                    # PnL after commission
                    if pnl_after_commission < 0:
                        color = "\033[91m"
                        indicator = "LOSS"
                    else:
                        color = "\033[92m"
                        indicator = "GAIN"
                    print(f"  {color}**{symbol}** [TWS Audit] Final PnL - Commission ${abs(pnl_after_commission):.2f} --- {indicator}{reset}")

                # Display appropriate prompt
                print(f"\n{'=' * 50}")

                if not order_placed:
                    # Phase 7: Open position prompt
                    print(
                        f"\033[93m **{symbol}** >>> Open Trade at ${quote.ask_price:.2f} (press enter) ?\033[0m ",
                        end="",
                        flush=True,
                    )

                    # Wait for Enter key with 1 second timeout
                    ready = select.select([sys.stdin], [], [], 1.0)[0]

                    if ready:
                        # User pressed Enter
                        user_input = sys.stdin.readline()

                        print(
                            f"\n\033[92mPlacing LIMIT order for {position_size} shares of {symbol} at ${quote.ask_price:.2f}...\033[0m"
                        )

                        # Place limit order at ask price
                        result = client.place_limit_order(
                            symbol, "BUY", position_size, quote.ask_price
                        )

                        if result:
                            print(f"✅ Order placed successfully!")
                            print(f"   Order ID: {result.order_id}")
                            print(f"   Type: LIMIT @ ${result.limit_price:.2f}")
                            order_placed = True

                            # Monitor order status until filled
                            order_filled = monitor_order_status(
                                client, result, symbol, order_type="Open"
                            )
                            if order_filled:
                                filled_order = result
                        else:
                            print("❌ Failed to place order")
                            time.sleep(2)
                    else:
                        # No input within 1 second, refresh automatically
                        continue

                elif order_filled and not position_closed:
                    # Phase 8: Close position prompt
                    print(
                        f"\033[93m **{symbol}** >>> Close position at ${quote.bid_price:.2f} (press enter)?\033[0m ",
                        end="",
                        flush=True,
                    )

                    # Wait for Enter key with 1 second timeout
                    ready = select.select([sys.stdin], [], [], 1.0)[0]

                    if ready:
                        # User pressed Enter - close position
                        user_input = sys.stdin.readline()

                        if symbol in client.positions:
                            position = client.positions[symbol]
                            position_closed, close_order = place_sell_order(
                                client, symbol, position["quantity"], quote.bid_price
                            )

                            if position_closed:
                                print("\n✅ Position closed successfully!")
                                # Automatically perform audit
                                time.sleep(2)
                                perform_audit(client, symbol)
                                audit_complete = True
                                time.sleep(3)
                        else:
                            print("\n⚠️ No position found to close")
                            time.sleep(2)
                    else:
                        # No input - refresh and show PnL
                        continue

                elif position_closed and audit_complete:
                    # Phase 10: Exit trade prompt
                    print(
                        f"\033[93m **{symbol}** >>> Exit the trade (press enter)?\033[0m ",
                        end="",
                        flush=True,
                    )

                    # Wait for Enter key with 1 second timeout
                    ready = select.select([sys.stdin], [], [], 1.0)[0]

                    if ready:
                        # User pressed Enter - exit trade
                        user_input = sys.stdin.readline()
                        print("\n✅ Exiting trade and returning to menu...")
                        time.sleep(2)
                        break
                    else:
                        # No input - continue displaying
                        continue
                else:
                    # Waiting state
                    print("Monitoring... (Ctrl+C to exit)")
                    time.sleep(1)

            else:
                print("\n  ❌ No data available")
                print(f"\n{'=' * 50}")
                print("Waiting for data... (Ctrl+C to exit)")
                time.sleep(2)

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
        if order_placed:
            if order_filled and not position_closed:
                print("Note: Your position remains open.")
            elif not order_filled:
                print("Note: Your order was placed and will continue to execute.")
        input("Press Enter to continue...")


def parse_arguments():
    """Parse command-line arguments for symbol and position size"""
    parser = argparse.ArgumentParser(
        description="IBXPy Trading Application - Trade stocks via Interactive Brokers TWS"
    )
    parser.add_argument("symbol", type=str, help="Stock symbol to trade (e.g., AAPL)")
    parser.add_argument("position_size", type=int, help="Number of shares to trade")
    return parser.parse_args()


def main():
    """Main application entry point with command-line arguments"""
    # Parse command-line arguments
    try:
        args = parse_arguments()
    except SystemExit:
        print("\n❌ Error: Both symbol and position size are required")
        print("Usage: python main.py <symbol> <position_size>")
        print("Example: python main.py AAPL 100")
        sys.exit(1)

    # Convert symbol to uppercase
    symbol = args.symbol.upper()
    position_size = args.position_size

    # Validate position size
    if position_size <= 0:
        print("\n❌ Error: Position size must be greater than 0")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("IBX AI Trading Application")
    print("Phase 11 - Command-line Arguments")
    print("=" * 50)
    print(f"Symbol: {symbol}")
    print(f"Position Size: {position_size} shares")

    # Create and connect OrderClient
    print("\nConnecting to TWS on port 7500...")
    client = OrderClient()

    try:
        if not client.connect_to_tws(host="127.0.0.1", port=7500, client_id=1):
            print("❌ Failed to connect to TWS")
            print("Please ensure TWS is running and API connections are enabled")
            sys.exit(1)

        print("✅ Successfully connected to TWS!")
        print(f"Next Order ID: {client.next_order_id}")
        time.sleep(1)

        # Main application loop
        while True:
            try:
                clear_screen()
                display_menu(symbol, position_size)
                choice = input().strip()

                if choice == "1":
                    begin_trading(client, symbol, position_size)
                elif choice == "2":
                    print("\nDisconnecting from TWS...")
                    break
                else:
                    print("\nInvalid choice. Please try again.")
                    time.sleep(1)

            except KeyboardInterrupt:
                print("\n\nReturning to main menu...")
                time.sleep(1)
                continue

    except ImportError as e:
        logger.error(f"Import error: {e}")
        print("\n❌ ibapi package not found!")
        print("Please run ./install_ibapi.sh to install the IB API")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        # Always disconnect
        if client and client.is_connected():
            client.disconnect_from_tws()
            print("Disconnected from TWS")
        print("Goodbye!")


if __name__ == "__main__":
    main()

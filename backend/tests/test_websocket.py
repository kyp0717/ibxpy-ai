"""Test WebSocket functionality.

Run this test with the server running:
    python tests/test_websocket.py
"""
import asyncio
import json
import msgpack
import websockets
from datetime import datetime


async def test_json_connection():
    """Test WebSocket connection with JSON protocol."""
    uri = "ws://localhost:8001/ws/market?client_id=test_client_json&binary=false"
    
    async with websockets.connect(uri) as websocket:
        print("Connected with JSON protocol")
        
        # Wait for connection message
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Received: {data}")
        
        # Subscribe to symbols
        subscribe_msg = {
            "type": "subscribe",
            "symbols": ["AAPL", "GOOGL", "MSFT"]
        }
        await websocket.send(json.dumps(subscribe_msg))
        
        # Wait for subscription confirmation
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Subscription response: {data}")
        
        # Send ping
        ping_msg = {"type": "ping"}
        await websocket.send(json.dumps(ping_msg))
        
        # Wait for pong
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Ping response: {data}")
        
        # Unsubscribe from a symbol
        unsubscribe_msg = {
            "type": "unsubscribe",
            "symbols": ["GOOGL"]
        }
        await websocket.send(json.dumps(unsubscribe_msg))
        
        # Wait for unsubscription confirmation
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Unsubscribe response: {data}")
        
        print("JSON test completed successfully!")


async def test_msgpack_connection():
    """Test WebSocket connection with msgpack binary protocol."""
    uri = "ws://localhost:8001/ws/market?client_id=test_client_binary&binary=true"
    
    async with websockets.connect(uri) as websocket:
        print("\nConnected with msgpack protocol")
        
        # Wait for connection message
        message = await websocket.recv()
        data = msgpack.unpackb(message, raw=False)
        print(f"Received: {data}")
        
        # Subscribe to symbols
        subscribe_msg = {
            "type": "subscribe",
            "symbols": ["TSLA", "AMZN", "META"]
        }
        await websocket.send(msgpack.packb(subscribe_msg))
        
        # Wait for subscription confirmation
        message = await websocket.recv()
        data = msgpack.unpackb(message, raw=False)
        print(f"Subscription response: {data}")
        
        # Send ping
        ping_msg = {"type": "ping"}
        await websocket.send(msgpack.packb(ping_msg))
        
        # Wait for pong
        message = await websocket.recv()
        data = msgpack.unpackb(message, raw=False)
        print(f"Ping response: {data}")
        
        print("Msgpack test completed successfully!")


async def test_order_websocket():
    """Test order updates WebSocket."""
    uri = "ws://localhost:8001/ws/orders?client_id=test_order_client"
    
    async with websockets.connect(uri) as websocket:
        print("\nConnected to order updates WebSocket")
        
        # Send ping
        ping_msg = {"type": "ping"}
        await websocket.send(json.dumps(ping_msg))
        
        # Wait for pong
        message = await websocket.recv()
        data = json.loads(message)
        print(f"Order WS ping response: {data}")
        
        print("Order WebSocket test completed successfully!")


async def test_multiple_clients():
    """Test multiple concurrent WebSocket connections."""
    clients = []
    
    # Create 5 concurrent connections
    for i in range(5):
        uri = f"ws://localhost:8001/ws/market?client_id=client_{i}&binary=false"
        ws = await websockets.connect(uri)
        clients.append(ws)
        
    print(f"\n{len(clients)} clients connected")
    
    # Each client subscribes to different symbols
    for i, ws in enumerate(clients):
        subscribe_msg = {
            "type": "subscribe",
            "symbols": [f"SYM{i}"]
        }
        await ws.send(json.dumps(subscribe_msg))
        
    # Wait for responses
    for ws in clients:
        message = await ws.recv()  # Connection message
        message = await ws.recv()  # Subscription confirmation
        
    print("All clients subscribed")
    
    # Close all connections
    for ws in clients:
        await ws.close()
        
    print("Multiple client test completed successfully!")


async def main():
    """Run all WebSocket tests."""
    print("=" * 50)
    print("WebSocket Test Suite")
    print("=" * 50)
    print(f"Started at: {datetime.now().isoformat()}\n")
    
    try:
        # Test JSON protocol
        await test_json_connection()
        
        # Test msgpack protocol
        await test_msgpack_connection()
        
        # Test order WebSocket
        await test_order_websocket()
        
        # Test multiple clients
        await test_multiple_clients()
        
        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
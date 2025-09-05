# IBAPI Configuration and Location

## Current IBAPI Installation Location

**IMPORTANT**: The IBAPI package is installed from a local directory, not from PyPI.

### Known Installation Paths (Check these in order):
1. `~/Downloads/twsapi/IBJts/source/pythonclient/`
2. `~/Downloads/TWS_API/source/pythonclient/`
3. `~/Downloads/twsapi_macunix/IBJts/source/pythonclient/`
4. `~/Downloads/twsapi_linux/IBJts/source/pythonclient/`

### To Find Your IBAPI Location:
```bash
# Check if IBAPI is installed in virtual environment
python -c "import ibapi; print(ibapi.__file__)"

# Find the source directory
find ~/Downloads -name "pythonclient" -type d 2>/dev/null | grep -i tws
```

### Verified Installation Path (Update this):
```
# TODO: Update with actual path after verification
IBAPI_SOURCE_PATH = ~/Downloads/twsapi/IBJts/source/pythonclient/
```

## TWS/IBGateway Connection Settings

### Paper Trading (Default):
- Host: 127.0.0.1
- Port: 7497
- Client ID: 1

### Live Trading:
- Host: 127.0.0.1
- Port: 7496
- Client ID: 1

### IBGateway Paper:
- Host: 127.0.0.1
- Port: 4002
- Client ID: 1

### IBGateway Live:
- Host: 127.0.0.1
- Port: 4001
- Client ID: 1

## Backend Integration

When integrating IBAPI with the backend, ensure:

1. **Import Path**: The backend needs access to the installed IBAPI package
2. **Thread Safety**: IBAPI requires its own thread for message processing
3. **Connection Management**: Only one client ID can connect at a time

## Troubleshooting

### Common Issues:

1. **ImportError: No module named 'ibapi'**
   - Solution: Reinstall using `uv pip install ~/Downloads/twsapi/IBJts/source/pythonclient/`

2. **Connection refused on port 7497**
   - Solution: Ensure TWS/IBGateway is running and API connections are enabled

3. **Multiple client error**
   - Solution: Use different client IDs or disconnect other clients

## Testing IBAPI Connection

```python
# Quick test script
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        
    def error(self, reqId, errorCode, errorString):
        print(f"Error: {reqId} {errorCode} {errorString}")
        
    def nextValidId(self, orderId):
        print(f"Connected! Next valid order ID: {orderId}")

def run_test():
    app = TestApp()
    app.connect("127.0.0.1", 7497, clientId=999)
    app.run()

if __name__ == "__main__":
    thread = threading.Thread(target=run_test)
    thread.start()
    time.sleep(2)
    print("Test complete")
```
# Backend Architecture

## Overview

The backend is built with FastAPI to provide a high-performance, async-first architecture for the trading system. It maintains a dual-mode design where trading operations bypass the web layer for minimal latency.

## Core Design Principles

### 1. Performance First
- Direct TWS connection path for trading (<10ms latency)
- Binary protocol (msgpack) for WebSocket communication
- Redis caching for market data
- Connection pooling and reuse

### 2. Async Architecture
- Built on FastAPI/Starlette async framework
- Non-blocking I/O operations
- Concurrent request handling
- Event-driven message processing

### 3. Fault Tolerance
- Automatic reconnection logic
- Circuit breakers for external services
- Graceful degradation
- Health checks and monitoring

## Component Architecture

```
backend/
├── Core Layer
│   ├── Config Management (Pydantic Settings)
│   ├── Dependency Injection
│   ├── Exception Handling
│   └── Middleware Pipeline
├── API Layer
│   ├── REST Endpoints (FastAPI)
│   ├── WebSocket Manager
│   ├── Request Validation
│   └── Response Serialization
├── Service Layer
│   ├── TWS Service (IBAPI Wrapper)
│   ├── Trading Engine
│   ├── Market Data Processor
│   └── Position Tracker
└── Infrastructure Layer
    ├── Redis Cache
    ├── Performance Monitor
    ├── Logging Service
    └── Background Tasks
```

## Request Flow

### Trading Path (Critical, <10ms)
```python
# Direct execution path bypassing web layer
Trading Signal → Trading Engine → TWS Service → IBAPI → TWS
                     ↓
                Risk Check
                     ↓
              Order Validation
```

### Monitoring Path (Non-critical, 15-20ms)
```python
Market Data → Data Processor → Cache → WebSocket → Frontend
                  ↓
            Aggregation
                  ↓
            Calculation (EMA)
```

## Key Components

### 1. FastAPI Application (`main.py`)
- Application lifecycle management
- Middleware configuration
- Router registration
- Global exception handling

### 2. Configuration (`core/config.py`)
- Environment-based configuration
- Pydantic Settings for validation
- Type-safe configuration access
- Secret management

### 3. Dependencies (`core/dependencies.py`)
- Dependency injection container
- Connection managers
- Performance monitoring
- Shared resources

### 4. Health System (`api/health.py`)
- Liveness probes
- Readiness checks
- Component health monitoring
- Performance metrics

### 5. WebSocket Manager (Coming Soon)
```python
class WebSocketManager:
    - Connection pooling
    - Binary message protocol
    - Auto-reconnection
    - Broadcast capabilities
    - Rate limiting
```

### 6. Trading Engine (Coming Soon)
```python
class TradingEngine:
    - Order execution (<10ms)
    - Risk management
    - Position tracking
    - Order validation
    - Error handling
```

## Performance Optimizations

### 1. Connection Pooling
- Reuse TWS connections
- Redis connection pool
- WebSocket connection management

### 2. Caching Strategy
- Redis for market data
- In-memory caching for static data
- TTL-based cache invalidation

### 3. Async Operations
```python
# All I/O operations are async
async def get_market_data(symbol: str):
    # Non-blocking Redis lookup
    cached = await redis.get(f"market:{symbol}")
    if cached:
        return cached
    
    # Non-blocking TWS call
    data = await tws_service.get_quote(symbol)
    
    # Non-blocking cache update
    await redis.setex(f"market:{symbol}", 300, data)
    return data
```

### 4. Message Batching
```python
# Batch updates every 50ms
async def batch_broadcaster():
    while True:
        await asyncio.sleep(0.05)  # 50ms
        if pending_updates:
            await websocket.broadcast(
                msgpack.packb(pending_updates)
            )
            pending_updates.clear()
```

## Security Considerations

### 1. Authentication (Future)
- JWT tokens for session management
- API key authentication for services
- Rate limiting per client

### 2. Input Validation
- Pydantic models for request validation
- Type checking at runtime
- SQL injection prevention

### 3. Error Handling
- No sensitive data in error messages
- Structured error responses
- Audit logging for failures

## Monitoring & Observability

### 1. Health Endpoints
```
/health          - Basic health check
/health/live     - Kubernetes liveness
/health/ready    - Service readiness
/health/detailed - Component statuses
/health/metrics  - Performance metrics
```

### 2. Performance Tracking
```python
# Automatic latency tracking
@track_performance("order_execution")
async def place_order(order: Order):
    start = time.perf_counter()
    result = await tws_service.place_order(order)
    latency_ms = (time.perf_counter() - start) * 1000
    
    if latency_ms > MAX_LATENCY_MS:
        logger.warning(f"Slow order execution: {latency_ms}ms")
    
    return result
```

### 3. Structured Logging
```json
{
  "time": "2024-01-05T10:30:00Z",
  "level": "INFO",
  "msg": "Order executed",
  "order_id": "12345",
  "symbol": "AAPL",
  "latency_ms": 7.2,
  "correlation_id": "abc-123"
}
```

## Deployment

### Development
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Testing Strategy

### 1. Unit Tests
- Test individual components
- Mock external dependencies
- Focus on business logic

### 2. Integration Tests
- Test component interactions
- Use test database/cache
- Verify API contracts

### 3. Performance Tests
- Load testing with Locust
- Latency measurements
- Stress testing

### 4. End-to-End Tests
- Full system flow
- Real TWS paper account
- Production-like environment
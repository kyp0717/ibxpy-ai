# Trading Backend - FastAPI

High-performance backend for the hybrid trading architecture with <10ms execution latency.

## Architecture

The backend implements a dual-mode system:
- **Trading Path**: Direct Python → TWS execution (<10ms)
- **Monitoring Path**: Python → WebSocket → React (15-20ms acceptable)

## Quick Start

### 1. Install Dependencies

```bash
# ALWAYS activate virtual environment first
source .venv/bin/activate

# Then install backend dependencies
cd backend
uv pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the backend directory:

```env
# Application
DEBUG=true
LOG_LEVEL=INFO

# Server
HOST=0.0.0.0
PORT=8000

# TWS Connection
TWS_HOST=127.0.0.1
TWS_PORT=7497  # Paper trading port
TWS_CLIENT_ID=1

# Redis (optional)
REDIS_URL=redis://localhost:6379

# Performance
MAX_LATENCY_MS=10
BATCH_UPDATE_INTERVAL_MS=50
```

### 3. Run the Server

Development mode (with auto-reload):
```bash
# Ensure virtual environment is active
source ../.venv/bin/activate  # (if not already active)
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Production mode:
```bash
# Ensure virtual environment is active
source ../.venv/bin/activate
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

### Health Checks

- `GET /` - Root endpoint with basic info
- `GET /health` - Basic health check
- `GET /health/live` - Kubernetes liveness probe
- `GET /health/ready` - Kubernetes readiness probe
- `GET /health/detailed` - Detailed health with component statuses
- `GET /health/metrics` - Performance metrics

### API Documentation

When running in debug mode:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI Schema: http://localhost:8000/openapi.json

## Project Structure

```
backend/
├── main.py              # FastAPI application entry
├── core/
│   ├── config.py       # Settings management
│   ├── dependencies.py # Dependency injection
│   └── exceptions.py   # Custom exceptions
├── api/
│   ├── health.py       # Health check endpoints
│   └── websocket.py    # WebSocket endpoints (coming soon)
├── services/
│   ├── tws_service.py     # TWS integration (coming soon)
│   ├── trading_engine.py  # Trading logic (coming soon)
│   └── market_data.py     # Market data service (coming soon)
└── requirements.txt    # Python dependencies
```

## Performance Targets

- Order Execution: <10ms (Python to TWS)
- API Response: <50ms
- WebSocket Latency: <20ms
- Throughput: 1000+ updates/second

## Development

### Testing

Run tests:
```bash
# Always in virtual environment
source ../.venv/bin/activate
cd backend
pytest
```

Run with coverage:
```bash
source ../.venv/bin/activate
cd backend
pytest --cov=backend
```

### Code Quality

Format code:
```bash
black .
isort .
```

Type checking:
```bash
mypy .
```

## Monitoring

The backend provides comprehensive monitoring through:

1. **Health Endpoints** - Component status checks
2. **Performance Metrics** - Latency tracking
3. **Structured Logging** - JSON format for log aggregation
4. **Response Headers** - X-Process-Time-ms header

## Next Steps

- [ ] Implement WebSocket manager
- [ ] Integrate TWS connection
- [ ] Add Redis caching
- [ ] Implement trading engine
- [ ] Add market data streaming
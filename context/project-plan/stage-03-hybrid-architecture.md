# Stage 03 - Hybrid Architecture Implementation

## Overview
Build a dual-mode trading system with low-latency Python backend for trading execution (<10ms) and React web frontend for monitoring and visualization.

## Architecture Principles
- **Trading Path**: Direct Python → TWS execution (no web layer involvement)
- **Monitoring Path**: Python → WebSocket → React (acceptable 15-20ms latency)
- **Performance First**: Binary protocols, caching, and optimized data flow
- **Separation of Concerns**: Trading logic stays in Python, UI is purely for display

## Phase 01 - Backend Infrastructure Setup
### Feature 1: FastAPI Server Foundation
- Create backend/ directory structure
- Setup FastAPI application with uvicorn
- Configure CORS for frontend access
- Implement health check endpoints

### Feature 2: WebSocket Manager
- Create WebSocket connection manager
- Implement connection pooling
- Setup binary message protocol (msgpack)
- Handle multiple client connections

### Test 1: Server and WebSocket
- Verify FastAPI server startup
- Test WebSocket connections
- Validate message encoding/decoding
- Measure baseline latencies

## Phase 02 - Trading Engine Integration
### Feature 1: TWS Service Wrapper
- Wrap existing connection.py module
- Create async wrapper for IBAPI calls
- Implement connection state management
- Add automatic reconnection logic

### Feature 2: Direct Trading Engine
- Create TradingEngine class for order execution
- Implement risk management checks
- Add position tracking service
- Ensure <10ms execution path

### Test 2: Trading Engine Performance
- Measure order execution latency
- Test risk management rules
- Verify position tracking accuracy
- Stress test with multiple orders

## Phase 03 - Real-time Data Streaming
### Feature 1: Market Data Service
- Integrate five_second_bars.py module
- Create data aggregation service (5s → 1min)
- Implement EMA calculation service
- Setup Redis cache for market data

### Feature 2: WebSocket Data Streaming
- Stream 5-second bars via WebSocket
- Push 1-minute aggregated bars
- Broadcast EMA updates
- Implement data batching (50ms intervals)

### Test 3: Data Streaming
- Verify 5-second bar streaming
- Test 1-minute aggregation accuracy
- Validate EMA calculations
- Measure streaming latencies

## Phase 04 - REST API Development
### Feature 1: Trading Endpoints
- POST /api/orders - Place orders
- GET /api/positions - Get positions
- DELETE /api/orders/{id} - Cancel orders
- GET /api/account - Account info

### Feature 2: Market Data Endpoints
- GET /api/market-data/{symbol} - Latest prices
- GET /api/bars/{symbol} - Historical bars
- GET /api/indicators/{symbol} - Technical indicators

### Test 4: API Integration
- Test all REST endpoints
- Validate response formats
- Check error handling
- Measure API response times

## Phase 05 - Frontend Foundation
### Feature 1: React Application Setup
- Initialize React with TypeScript
- Configure build tools (Vite/CRA)
- Setup TailwindCSS for styling
- Create project structure

### Feature 2: WebSocket Client
- Implement WebSocket connection handler
- Create reconnection logic
- Setup message decoding (msgpack)
- Implement connection status indicator

### Test 5: Frontend Infrastructure
- Test WebSocket connection
- Verify message handling
- Check reconnection logic
- Validate TypeScript configuration

## Phase 06 - Trading Dashboard UI
### Feature 1: Real-time Price Display
- Create price ticker component
- Implement bid/ask spread display
- Show last trade information
- Add price change indicators

### Feature 2: Chart Components
- Integrate charting library (Recharts/TradingView)
- Display 5-second bar chart
- Show 1-minute candlestick chart
- Overlay EMA indicator

### Test 6: Dashboard Components
- Test real-time updates
- Verify chart rendering
- Check data accuracy
- Measure UI responsiveness

## Phase 07 - Position & Order Management UI
### Feature 1: Position Display
- Create positions table
- Show real-time P&L
- Display position details
- Add position summary card

### Feature 2: Order Interface
- Build order placement form
- Show order status updates
- Create order history table
- Add order modification controls

### Test 7: Trading Interface
- Test order placement flow
- Verify position updates
- Check P&L calculations
- Validate order status tracking

## Phase 08 - Performance Optimization
### Feature 1: Backend Optimization
- Implement connection pooling
- Optimize database queries
- Add response caching
- Profile and optimize hot paths

### Feature 2: Frontend Optimization
- Implement React.memo for components
- Add virtual scrolling for lists
- Optimize re-renders
- Implement lazy loading

### Test 8: Performance Testing
- Load test with 1000+ updates/sec
- Measure end-to-end latencies
- Profile memory usage
- Test with multiple concurrent users

## Phase 09 - Integration & Deployment
### Feature 1: Docker Configuration
- Create Dockerfile for backend
- Create Dockerfile for frontend
- Setup docker-compose.yml
- Configure environment variables

### Feature 2: Production Setup
- Setup nginx reverse proxy
- Configure SSL certificates
- Implement logging aggregation
- Add monitoring/alerting

### Test 9: End-to-End Testing
- Test complete trading flow
- Verify all integrations
- Run stress tests
- Validate production configuration

## Phase 10 - Documentation & Handoff
### Feature 1: Technical Documentation
- API documentation (OpenAPI/Swagger)
- WebSocket event documentation
- Deployment guide
- Performance tuning guide

### Feature 2: User Documentation
- User interface guide
- Trading workflow documentation
- Troubleshooting guide
- Configuration reference

### Test 10: Documentation Review
- Verify all endpoints documented
- Test deployment procedures
- Validate configuration steps
- Review troubleshooting guides

## Success Metrics
- Order execution latency: <10ms (Python to TWS)
- Market data latency: <20ms (Python to React)
- System uptime: 99.9% during market hours
- WebSocket stability: <1% disconnection rate
- UI responsiveness: 60fps for charts
- Load capacity: 1000+ updates/second
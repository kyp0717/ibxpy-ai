"""
Main FastAPI application for the trading backend
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.config import settings
from backend.core.exceptions import TradingException
from backend.api import health, websocket, trading, market_data, orders, state, monitoring
from backend.services.websocket_service import websocket_service
from backend.services.trading_engine import trading_engine

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' if settings.log_format == "text" 
           else '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","msg":"%(message)s"}'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Server: {settings.host}:{settings.port}")
    logger.info(f"TWS connection: {settings.get_tws_connection_string()}")
    
    # Start WebSocket service
    await websocket_service.start()
    logger.info("WebSocket service started")
    
    # Start Trading Engine (connects to TWS)
    try:
        await trading_engine.start()
        logger.info("Trading engine started successfully")
    except Exception as e:
        logger.warning(f"Trading engine start failed (TWS may not be running): {e}")
    
    # TODO: Connect to Redis
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Stop Trading Engine
    try:
        await trading_engine.stop()
        logger.info("Trading engine stopped")
    except Exception as e:
        logger.error(f"Error stopping trading engine: {e}")
    
    # Stop WebSocket service
    await websocket_service.stop()
    
    # TODO: Close Redis connections


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="High-performance backend for hybrid trading system with <10ms execution latency",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add routers
app.include_router(health.router)
app.include_router(websocket.router)
app.include_router(trading.router)
app.include_router(market_data.router)
app.include_router(orders.router)
app.include_router(state.router)
app.include_router(monitoring.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "health": "/health"
    }

# Global exception handler
@app.exception_handler(TradingException)
async def trading_exception_handler(request, exc: TradingException):
    """Handle trading-specific exceptions"""
    logger.error(f"Trading exception: {exc.message}", extra={"details": exc.details})
    return JSONResponse(
        status_code=500,
        content={
            "error": exc.message,
            "details": exc.details,
            "type": exc.__class__.__name__
        }
    )

# Performance middleware
@app.middleware("http")
async def add_performance_headers(request, call_next):
    """Add performance monitoring headers"""
    import time
    start_time = time.perf_counter()
    
    response = await call_next(request)
    
    process_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
    response.headers["X-Process-Time-ms"] = str(process_time)
    
    # Log slow requests
    if process_time > settings.max_latency_ms:
        logger.warning(
            f"Slow request: {request.method} {request.url.path} took {process_time:.2f}ms"
        )
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
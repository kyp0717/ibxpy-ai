"""Connection recovery service for handling TWS disconnections.

Provides automatic reconnection, state recovery, and subscription restoration
after connection failures.
"""
import asyncio
import logging
from typing import Dict, Set, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field

from ..core.error_handler import error_handler, ErrorSeverity
from ..core.exceptions import TradingException
from .websocket_service import websocket_service

logger = logging.getLogger(__name__)


class RecoveryState(Enum):
    """Connection recovery states."""
    IDLE = "IDLE"
    RECOVERING = "RECOVERING"
    RECONNECTING = "RECONNECTING"
    RESTORING = "RESTORING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RecoveryContext:
    """Context information for recovery process."""
    attempt: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_attempt: Optional[datetime] = None
    error_count: int = 0
    subscriptions: Set[str] = field(default_factory=set)
    pending_orders: List[int] = field(default_factory=list)
    last_known_state: Dict[str, Any] = field(default_factory=dict)
    

class ConnectionRecoveryService:
    """Service for managing connection recovery and failover."""
    
    def __init__(self):
        self._recovery_state = RecoveryState.IDLE
        self._recovery_task: Optional[asyncio.Task] = None
        self._recovery_context: Optional[RecoveryContext] = None
        self._recovery_callbacks: Dict[str, Callable] = {}
        self._max_recovery_attempts = 5
        self._recovery_interval = 30  # seconds
        self._health_check_interval = 10  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._tws_service = None  # Will be injected
        self._running = False
        
    def set_tws_service(self, tws_service):
        """Set reference to TWS service."""
        self._tws_service = tws_service
        
    def register_recovery_callback(self, name: str, callback: Callable):
        """Register a callback to be called during recovery.
        
        Args:
            name: Unique name for the callback
            callback: Async function to call during recovery
        """
        self._recovery_callbacks[name] = callback
        logger.debug(f"Registered recovery callback: {name}")
        
    async def start(self):
        """Start the recovery service."""
        if self._running:
            return
            
        self._running = True
        self._recovery_state = RecoveryState.IDLE
        
        # Start health check loop
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info("Connection recovery service started")
        
    async def stop(self):
        """Stop the recovery service."""
        if not self._running:
            return
            
        self._running = False
        
        # Cancel tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
                
        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Connection recovery service stopped")
        
    async def trigger_recovery(self, error: Optional[Exception] = None):
        """Trigger connection recovery process.
        
        Args:
            error: Optional exception that triggered recovery
        """
        if self._recovery_state == RecoveryState.RECOVERING:
            logger.warning("Recovery already in progress")
            return
            
        logger.info(f"Triggering connection recovery. Error: {error}")
        
        # Record error
        if error:
            error_handler.record_error(
                error_type="CONNECTION_LOST",
                message=str(error),
                severity=ErrorSeverity.HIGH,
                context={"trigger": "manual"}
            )
            
        # Start recovery
        self._recovery_task = asyncio.create_task(self._recovery_process())
        
    async def _recovery_process(self):
        """Main recovery process."""
        self._recovery_state = RecoveryState.RECOVERING
        self._recovery_context = RecoveryContext()
        
        try:
            # Broadcast recovery started
            await websocket_service.broadcast_market_data(
                "SYSTEM",
                {
                    "type": "recovery_started",
                    "data": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "state": self._recovery_state.value
                    }
                }
            )
            
            # Save current state
            await self._save_state()
            
            # Attempt reconnection
            success = await self._attempt_reconnection()
            
            if success:
                # Restore state
                await self._restore_state()
                
                # Mark recovery as completed
                self._recovery_state = RecoveryState.COMPLETED
                
                # Broadcast recovery completed
                await websocket_service.broadcast_market_data(
                    "SYSTEM",
                    {
                        "type": "recovery_completed",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "attempts": self._recovery_context.attempt,
                            "duration_seconds": (
                                datetime.utcnow() - self._recovery_context.start_time
                            ).total_seconds()
                        }
                    }
                )
                
                logger.info(f"Recovery completed after {self._recovery_context.attempt} attempts")
                
            else:
                self._recovery_state = RecoveryState.FAILED
                
                # Broadcast recovery failed
                await websocket_service.broadcast_market_data(
                    "SYSTEM",
                    {
                        "type": "recovery_failed",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "attempts": self._recovery_context.attempt,
                            "max_attempts": self._max_recovery_attempts
                        }
                    }
                )
                
                logger.error(f"Recovery failed after {self._recovery_context.attempt} attempts")
                
                # Record failure
                error_handler.record_error(
                    error_type="RECOVERY_FAILED",
                    message="Connection recovery failed after maximum attempts",
                    severity=ErrorSeverity.CRITICAL,
                    context={"attempts": self._recovery_context.attempt}
                )
                
        except Exception as e:
            logger.error(f"Error in recovery process: {e}")
            self._recovery_state = RecoveryState.FAILED
            
        finally:
            self._recovery_context = None
            
    async def _save_state(self):
        """Save current state before disconnection."""
        if not self._tws_service:
            return
            
        try:
            from .state_manager import state_manager
            from .order_manager import order_manager
            
            # Save positions and accounts
            state = await state_manager.get_full_state()
            self._recovery_context.last_known_state = state
            
            # Save active orders
            orders = order_manager.get_all_orders()
            self._recovery_context.pending_orders = [
                order["order_id"] for order in orders 
                if order["status"] in ["PENDING", "SUBMITTED", "PARTIALLY_FILLED"]
            ]
            
            # Save subscriptions (would need to track these)
            # self._recovery_context.subscriptions = ...
            
            logger.info(f"Saved state: {len(self._recovery_context.pending_orders)} pending orders")
            
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            
    async def _attempt_reconnection(self) -> bool:
        """Attempt to reconnect to TWS.
        
        Returns:
            True if reconnection successful
        """
        if not self._tws_service:
            return False
            
        self._recovery_state = RecoveryState.RECONNECTING
        
        for attempt in range(1, self._max_recovery_attempts + 1):
            self._recovery_context.attempt = attempt
            self._recovery_context.last_attempt = datetime.utcnow()
            
            logger.info(f"Reconnection attempt {attempt}/{self._max_recovery_attempts}")
            
            try:
                # Disconnect if connected
                await self._tws_service.disconnect()
                
                # Wait before reconnecting
                await asyncio.sleep(2)
                
                # Attempt connection
                connected = await self._tws_service.connect()
                
                if connected:
                    logger.info(f"Reconnection successful on attempt {attempt}")
                    return True
                    
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt} failed: {e}")
                self._recovery_context.error_count += 1
                
            # Wait before next attempt (exponential backoff)
            if attempt < self._max_recovery_attempts:
                wait_time = min(2 ** attempt, 60)  # Max 60 seconds
                logger.info(f"Waiting {wait_time} seconds before next attempt")
                await asyncio.sleep(wait_time)
                
        return False
        
    async def _restore_state(self):
        """Restore state after reconnection."""
        if not self._recovery_context:
            return
            
        self._recovery_state = RecoveryState.RESTORING
        
        try:
            logger.info("Restoring state after reconnection")
            
            # Run recovery callbacks
            for name, callback in self._recovery_callbacks.items():
                try:
                    logger.debug(f"Running recovery callback: {name}")
                    await callback(self._recovery_context)
                except Exception as e:
                    logger.error(f"Error in recovery callback {name}: {e}")
                    
            # Request position updates
            if self._tws_service:
                await self._tws_service.request_positions()
                await self._tws_service.request_account_summary()
                
            # Re-request open orders
            # This would need implementation in TWS service
            # await self._tws_service.request_open_orders()
            
            # Restore market data subscriptions
            # This would need tracking of subscriptions
            # for symbol in self._recovery_context.subscriptions:
            #     await self._restore_subscription(symbol)
                
            logger.info("State restoration completed")
            
        except Exception as e:
            logger.error(f"Error restoring state: {e}")
            
    async def _health_check_loop(self):
        """Periodic health check of TWS connection."""
        while self._running:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                if not self._tws_service:
                    continue
                    
                # Check connection status
                status = self._tws_service.get_connection_status()
                
                if not status["connected"] and self._recovery_state == RecoveryState.IDLE:
                    logger.warning("Connection lost detected by health check")
                    await self.trigger_recovery()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        """Get recovery service status.
        
        Returns:
            Status dictionary
        """
        status = {
            "running": self._running,
            "recovery_state": self._recovery_state.value,
            "is_recovering": self._recovery_state != RecoveryState.IDLE,
            "max_attempts": self._max_recovery_attempts,
            "health_check_interval": self._health_check_interval
        }
        
        if self._recovery_context:
            status.update({
                "current_attempt": self._recovery_context.attempt,
                "recovery_started": self._recovery_context.start_time.isoformat(),
                "last_attempt": (
                    self._recovery_context.last_attempt.isoformat() 
                    if self._recovery_context.last_attempt else None
                ),
                "error_count": self._recovery_context.error_count
            })
            
        return status


# Global recovery service instance
connection_recovery = ConnectionRecoveryService()
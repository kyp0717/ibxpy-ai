"""State manager service for maintaining system-wide trading state.

This service manages positions, account data, and overall trading state,
ensuring consistency across all components.
"""
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import logging
import json

from ..core.config import settings
from ..core.exceptions import TradingException
from .websocket_service import websocket_service

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Trading mode enumeration."""
    PAPER = "PAPER"
    LIVE = "LIVE"
    SIMULATION = "SIMULATION"


class SystemState(Enum):
    """System state enumeration."""
    INITIALIZING = "INITIALIZING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class Position:
    """Position information."""
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    account: str
    last_update: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['last_update'] = self.last_update.isoformat()
        return data


@dataclass
class AccountData:
    """Account information."""
    account_id: str
    account_type: str
    currency: str
    cash_balance: float
    total_value: float
    buying_power: float
    maintenance_margin: float
    available_funds: float
    pnl_realized: float
    pnl_unrealized: float
    last_update: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data['last_update'] = self.last_update.isoformat()
        return data


@dataclass
class RiskMetrics:
    """Risk management metrics."""
    total_exposure: float
    position_count: int
    largest_position_symbol: Optional[str]
    largest_position_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    margin_usage_percent: float
    risk_score: float  # 0-100, higher is riskier
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class TradingSession:
    """Trading session information."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    mode: TradingMode
    initial_balance: float
    current_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_drawdown: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamps."""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        data['mode'] = self.mode.value
        return data


class StateManager:
    """Manages global trading state and synchronization."""
    
    def __init__(self):
        self._positions: Dict[str, Position] = {}
        self._accounts: Dict[str, AccountData] = {}
        self._system_state = SystemState.DISCONNECTED
        self._trading_mode = TradingMode.PAPER
        self._current_session: Optional[TradingSession] = None
        self._risk_metrics: Optional[RiskMetrics] = None
        self._subscribed_symbols: Set[str] = set()
        self._state_lock = asyncio.Lock()
        self._snapshot_interval = 60  # seconds
        self._snapshot_task: Optional[asyncio.Task] = None
        self._running = False
        
    async def start(self):
        """Start the state manager."""
        if self._running:
            return
            
        self._running = True
        self._system_state = SystemState.INITIALIZING
        
        # Start session
        await self._start_session()
        
        # Start snapshot task
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        
        logger.info("State manager started")
        
    async def stop(self):
        """Stop the state manager."""
        if not self._running:
            return
            
        self._running = False
        
        # End session
        await self._end_session()
        
        # Cancel snapshot task
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
                
        self._system_state = SystemState.DISCONNECTED
        logger.info("State manager stopped")
        
    async def _start_session(self):
        """Start a new trading session."""
        async with self._state_lock:
            self._current_session = TradingSession(
                session_id=f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                start_time=datetime.utcnow(),
                end_time=None,
                mode=self._trading_mode,
                initial_balance=0.0,
                current_balance=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                max_drawdown=0.0
            )
            
        logger.info(f"Started trading session: {self._current_session.session_id}")
        
    async def _end_session(self):
        """End the current trading session."""
        async with self._state_lock:
            if self._current_session:
                self._current_session.end_time = datetime.utcnow()
                
                # Broadcast session summary
                await websocket_service.broadcast_market_data(
                    "SYSTEM",
                    {
                        "type": "session_ended",
                        "data": self._current_session.to_dict()
                    }
                )
                
                logger.info(f"Ended trading session: {self._current_session.session_id}")
                
    async def set_system_state(self, state: SystemState):
        """Set system state."""
        async with self._state_lock:
            old_state = self._system_state
            self._system_state = state
            
        if old_state != state:
            logger.info(f"System state changed: {old_state.value} -> {state.value}")
            
            # Broadcast state change
            await websocket_service.broadcast_market_data(
                "SYSTEM",
                {
                    "type": "state_change",
                    "data": {
                        "old_state": old_state.value,
                        "new_state": state.value,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            
    async def update_position(self,
                            symbol: str,
                            quantity: float,
                            avg_cost: float,
                            current_price: float = 0.0,
                            account: str = "default") -> Position:
        """Update or create a position.
        
        Args:
            symbol: Trading symbol
            quantity: Position quantity (0 to close)
            avg_cost: Average cost basis
            current_price: Current market price
            account: Account identifier
            
        Returns:
            Updated Position object
        """
        async with self._state_lock:
            if quantity == 0 and symbol in self._positions:
                # Position closed
                position = self._positions.pop(symbol)
                logger.info(f"Position closed: {symbol}")
            else:
                # Calculate values
                market_value = quantity * current_price
                unrealized_pnl = (current_price - avg_cost) * quantity if quantity != 0 else 0.0
                
                position = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_cost=avg_cost,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=0.0,  # Updated separately
                    account=account,
                    last_update=datetime.utcnow()
                )
                
                self._positions[symbol] = position
                
            # Recalculate risk metrics
            await self._calculate_risk_metrics()
            
        # Broadcast position update
        await websocket_service.broadcast_position_update(
            account,
            [position.to_dict()] if quantity != 0 else []
        )
        
        return position
        
    async def update_account(self,
                           account_id: str,
                           account_data: Dict[str, Any]) -> AccountData:
        """Update account information.
        
        Args:
            account_id: Account identifier
            account_data: Account data dictionary
            
        Returns:
            Updated AccountData object
        """
        async with self._state_lock:
            account = AccountData(
                account_id=account_id,
                account_type=account_data.get('account_type', 'CASH'),
                currency=account_data.get('currency', 'USD'),
                cash_balance=account_data.get('cash_balance', 0.0),
                total_value=account_data.get('total_value', 0.0),
                buying_power=account_data.get('buying_power', 0.0),
                maintenance_margin=account_data.get('maintenance_margin', 0.0),
                available_funds=account_data.get('available_funds', 0.0),
                pnl_realized=account_data.get('pnl_realized', 0.0),
                pnl_unrealized=account_data.get('pnl_unrealized', 0.0),
                last_update=datetime.utcnow()
            )
            
            self._accounts[account_id] = account
            
            # Update session balance
            if self._current_session:
                if self._current_session.initial_balance == 0.0:
                    self._current_session.initial_balance = account.total_value
                self._current_session.current_balance = account.total_value
                
        # Broadcast account update
        await websocket_service.broadcast_market_data(
            "ACCOUNT",
            {
                "type": "account_update",
                "data": account.to_dict()
            }
        )
        
        return account
        
    async def record_trade_result(self, pnl: float):
        """Record trade result for session statistics.
        
        Args:
            pnl: Profit/loss from the trade
        """
        async with self._state_lock:
            if self._current_session:
                self._current_session.total_trades += 1
                self._current_session.total_pnl += pnl
                
                if pnl > 0:
                    self._current_session.winning_trades += 1
                else:
                    self._current_session.losing_trades += 1
                    
                # Update max drawdown
                if self._current_session.initial_balance > 0:
                    current_drawdown = (
                        (self._current_session.initial_balance - self._current_session.current_balance) 
                        / self._current_session.initial_balance * 100
                    )
                    self._current_session.max_drawdown = max(
                        self._current_session.max_drawdown,
                        current_drawdown
                    )
                    
    async def _calculate_risk_metrics(self):
        """Calculate risk management metrics."""
        if not self._positions:
            self._risk_metrics = RiskMetrics(
                total_exposure=0.0,
                position_count=0,
                largest_position_symbol=None,
                largest_position_value=0.0,
                total_unrealized_pnl=0.0,
                total_realized_pnl=0.0,
                margin_usage_percent=0.0,
                risk_score=0.0
            )
            return
            
        # Calculate metrics
        total_exposure = sum(abs(p.market_value) for p in self._positions.values())
        position_count = len(self._positions)
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())
        total_realized_pnl = sum(p.realized_pnl for p in self._positions.values())
        
        # Find largest position
        largest_position = max(self._positions.values(), key=lambda p: abs(p.market_value))
        
        # Calculate margin usage (simplified)
        total_account_value = sum(a.total_value for a in self._accounts.values()) or 1.0
        margin_usage_percent = (total_exposure / total_account_value) * 100 if total_account_value > 0 else 0
        
        # Calculate risk score (0-100)
        risk_factors = [
            min(position_count * 5, 30),  # More positions = higher risk
            min(margin_usage_percent / 2, 40),  # Higher margin = higher risk
            min(abs(total_unrealized_pnl / total_account_value) * 100, 30) if total_account_value > 0 else 0
        ]
        risk_score = sum(risk_factors)
        
        self._risk_metrics = RiskMetrics(
            total_exposure=total_exposure,
            position_count=position_count,
            largest_position_symbol=largest_position.symbol,
            largest_position_value=largest_position.market_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_realized_pnl=total_realized_pnl,
            margin_usage_percent=margin_usage_percent,
            risk_score=min(risk_score, 100)
        )
        
    async def _snapshot_loop(self):
        """Periodically save state snapshots."""
        while self._running:
            try:
                await asyncio.sleep(self._snapshot_interval)
                
                # Create snapshot
                snapshot = await self.get_full_state()
                
                # Broadcast snapshot
                await websocket_service.broadcast_market_data(
                    "SYSTEM",
                    {
                        "type": "state_snapshot",
                        "data": snapshot
                    }
                )
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in snapshot loop: {e}")
                
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position or None if not found
        """
        return self._positions.get(symbol)
        
    def get_all_positions(self) -> List[Position]:
        """Get all positions.
        
        Returns:
            List of all positions
        """
        return list(self._positions.values())
        
    def get_account(self, account_id: str) -> Optional[AccountData]:
        """Get account data.
        
        Args:
            account_id: Account identifier
            
        Returns:
            AccountData or None if not found
        """
        return self._accounts.get(account_id)
        
    def get_risk_metrics(self) -> Optional[RiskMetrics]:
        """Get current risk metrics.
        
        Returns:
            RiskMetrics or None if not calculated
        """
        return self._risk_metrics
        
    def get_session(self) -> Optional[TradingSession]:
        """Get current trading session.
        
        Returns:
            TradingSession or None if no active session
        """
        return self._current_session
        
    async def get_full_state(self) -> Dict[str, Any]:
        """Get complete system state.
        
        Returns:
            Complete state dictionary
        """
        async with self._state_lock:
            return {
                "system_state": self._system_state.value,
                "trading_mode": self._trading_mode.value,
                "positions": {
                    symbol: pos.to_dict() 
                    for symbol, pos in self._positions.items()
                },
                "accounts": {
                    acc_id: acc.to_dict()
                    for acc_id, acc in self._accounts.items()
                },
                "risk_metrics": self._risk_metrics.to_dict() if self._risk_metrics else None,
                "session": self._current_session.to_dict() if self._current_session else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            
    def get_status(self) -> Dict[str, Any]:
        """Get state manager status.
        
        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "system_state": self._system_state.value,
            "trading_mode": self._trading_mode.value,
            "position_count": len(self._positions),
            "account_count": len(self._accounts),
            "has_active_session": self._current_session is not None,
            "risk_score": self._risk_metrics.risk_score if self._risk_metrics else 0
        }


# Global state manager instance
state_manager = StateManager()
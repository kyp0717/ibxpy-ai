"""State management API endpoints.

Provides REST API for accessing system state, positions, accounts,
and risk metrics.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path
from pydantic import BaseModel, Field
import logging

from ..services.state_manager import state_manager
from ..services.trading_engine import trading_engine
from ..core.exceptions import TradingException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/state", tags=["state"])


class StateResponse(BaseModel):
    """Response model for system state."""
    system_state: str
    trading_mode: str
    position_count: int
    account_count: int
    risk_score: float
    timestamp: str


class RiskMetricsResponse(BaseModel):
    """Response model for risk metrics."""
    total_exposure: float
    position_count: int
    largest_position_symbol: Optional[str]
    largest_position_value: float
    total_unrealized_pnl: float
    total_realized_pnl: float
    margin_usage_percent: float
    risk_score: float


@router.get("/full")
async def get_full_state() -> Dict[str, Any]:
    """Get complete system state.
    
    Returns all positions, accounts, risk metrics, and session data.
    """
    try:
        full_state = await state_manager.get_full_state()
        return full_state
        
    except Exception as e:
        logger.error(f"Error fetching full state: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/positions")
async def get_all_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol")
) -> Dict[str, Any]:
    """Get all positions or a specific position.
    
    Returns current positions with P&L calculations.
    """
    try:
        if symbol:
            position = state_manager.get_position(symbol)
            if not position:
                raise HTTPException(status_code=404, detail=f"Position for {symbol} not found")
            positions = [position]
        else:
            positions = state_manager.get_all_positions()
            
        return {
            "positions": [pos.to_dict() for pos in positions],
            "count": len(positions),
            "total_unrealized_pnl": sum(p.unrealized_pnl for p in positions),
            "total_market_value": sum(p.market_value for p in positions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/positions/{symbol}")
async def get_position(
    symbol: str = Path(..., description="Trading symbol")
) -> Dict[str, Any]:
    """Get position details for a specific symbol."""
    try:
        position = state_manager.get_position(symbol)
        
        if not position:
            raise HTTPException(status_code=404, detail=f"Position for {symbol} not found")
            
        return position.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching position: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts")
async def get_all_accounts(
    account_id: Optional[str] = Query(None, description="Specific account ID")
) -> Dict[str, Any]:
    """Get all accounts or a specific account.
    
    Returns account balances and buying power information.
    """
    try:
        if account_id:
            account = state_manager.get_account(account_id)
            if not account:
                raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
            accounts = [account]
        else:
            # Get all accounts from positions
            accounts = []
            for position in state_manager.get_all_positions():
                account = state_manager.get_account(position.account)
                if account and account not in accounts:
                    accounts.append(account)
                    
        return {
            "accounts": [acc.to_dict() for acc in accounts],
            "count": len(accounts),
            "total_value": sum(a.total_value for a in accounts),
            "total_buying_power": sum(a.buying_power for a in accounts)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching accounts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/risk")
async def get_risk_metrics() -> RiskMetricsResponse:
    """Get current risk management metrics.
    
    Returns exposure, margin usage, and risk score.
    """
    try:
        metrics = state_manager.get_risk_metrics()
        
        if not metrics:
            # Return empty metrics
            return RiskMetricsResponse(
                total_exposure=0.0,
                position_count=0,
                largest_position_symbol=None,
                largest_position_value=0.0,
                total_unrealized_pnl=0.0,
                total_realized_pnl=0.0,
                margin_usage_percent=0.0,
                risk_score=0.0
            )
            
        return RiskMetricsResponse(**metrics.to_dict())
        
    except Exception as e:
        logger.error(f"Error fetching risk metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/session")
async def get_trading_session() -> Dict[str, Any]:
    """Get current trading session information.
    
    Returns session statistics including win rate and P&L.
    """
    try:
        session = state_manager.get_session()
        
        if not session:
            raise HTTPException(status_code=404, detail="No active trading session")
            
        session_dict = session.to_dict()
        
        # Calculate additional metrics
        if session.total_trades > 0:
            win_rate = (session.winning_trades / session.total_trades) * 100
            avg_pnl = session.total_pnl / session.total_trades
        else:
            win_rate = 0.0
            avg_pnl = 0.0
            
        session_dict.update({
            "win_rate": round(win_rate, 2),
            "average_pnl": round(avg_pnl, 2),
            "session_return": round(
                ((session.current_balance - session.initial_balance) / session.initial_balance * 100)
                if session.initial_balance > 0 else 0.0,
                2
            )
        })
        
        return session_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status")
async def get_state_status() -> StateResponse:
    """Get current state manager status.
    
    Returns system state and summary statistics.
    """
    try:
        status = state_manager.get_status()
        
        # Get current timestamp
        import datetime
        
        return StateResponse(
            system_state=status["system_state"],
            trading_mode=status["trading_mode"],
            position_count=status["position_count"],
            account_count=status["account_count"],
            risk_score=status["risk_score"],
            timestamp=datetime.datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error fetching state status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/record-trade")
async def record_trade_result(pnl: float = Query(..., description="Trade P&L")) -> Dict[str, Any]:
    """Record a trade result for session statistics.
    
    Updates win/loss counts and total P&L.
    """
    try:
        await state_manager.record_trade_result(pnl)
        
        return {
            "status": "recorded",
            "pnl": pnl,
            "type": "win" if pnl > 0 else "loss"
        }
        
    except Exception as e:
        logger.error(f"Error recording trade: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/snapshot")
async def get_state_snapshot() -> Dict[str, Any]:
    """Get a lightweight state snapshot.
    
    Returns summary information without full details.
    """
    try:
        positions = state_manager.get_all_positions()
        risk = state_manager.get_risk_metrics()
        session = state_manager.get_session()
        status = state_manager.get_status()
        
        return {
            "system_state": status["system_state"],
            "positions": {
                "count": len(positions),
                "total_value": sum(p.market_value for p in positions),
                "total_pnl": sum(p.unrealized_pnl for p in positions)
            },
            "risk": {
                "score": risk.risk_score if risk else 0,
                "exposure": risk.total_exposure if risk else 0,
                "margin_usage": risk.margin_usage_percent if risk else 0
            },
            "session": {
                "active": session is not None,
                "total_trades": session.total_trades if session else 0,
                "total_pnl": session.total_pnl if session else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching snapshot: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List, Any
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
from datetime import datetime

from db.models import UserTrade, UserTradeStatus
from services.trade_info import (
    get_trade_info, 
    get_execution_stats, 
    get_all_trades_summary
)
from db.db import Database

router = APIRouter(prefix="/trades", tags=["trades"])

# Pydantic models for request validation
class TradeCreate(BaseModel):
    symbol: str
    side: str
    total_quantity: float
    limit_price: float
    strategy: str
    strategy_params: Dict[str, Any]

class TradeResponse(BaseModel):
    trade_id: str
    message: str

@router.post("/", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
def create_new_trade(trade: TradeCreate, db: Session = Depends(Database.get_db)):
    """Create a new trade"""
    new_trade = UserTrade(
        id=str(uuid.uuid4()),
        symbol=trade.symbol,
        side=trade.side,
        total_quantity=trade.total_quantity,
        limit_price=trade.limit_price,
        strategy=trade.strategy,
        strategy_params=trade.strategy_params,
        status=UserTradeStatus.ACTIVE,
        timestamp=datetime.utcnow()
    )
    db.add(new_trade)
    db.commit()
    db.refresh(new_trade)
    return {"trade_id": new_trade.id, "message": "Trade created successfully"}

@router.get("/", response_model=List[Dict[str, Any]])
def list_all_trades(db: Session = Depends(Database.get_db)):
    """Get a summary of all trades"""
    return get_all_trades_summary(db)

@router.get("/{trade_id}", response_model=Dict[str, Any])
def get_trade_details(trade_id: str, db: Session = Depends(Database.get_db)):
    """Get detailed information about a specific trade"""
    trade = get_trade_info(db, trade_id)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with ID {trade_id} not found"
        )
    return trade

@router.get("/{trade_id}/stats", response_model=Dict[str, Any])
def get_trade_statistics(trade_id: str, db: Session = Depends(Database.get_db)):
    """Get execution statistics for a trade"""
    stats = get_execution_stats(db, trade_id)
    if "error" in stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=stats["error"]
        )
    return stats

@router.post("/{trade_id}/pause", response_model=Dict[str, Any])
def pause_existing_trade(trade_id: str, db: Session = Depends(Database.get_db)):
    """Pause an active trade"""
    trade = db.query(UserTrade).filter(UserTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with ID {trade_id} not found"
        )
    
    trade.status = UserTradeStatus.PAUSED
    db.commit()
    db.refresh(trade)
    
    if trade.status != UserTradeStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade with ID {trade_id} could not be paused. Current status: {trade.status.value}"
        )
    return {"trade_id": trade.id, "status": trade.status.value, "message": "Trade paused successfully"}

@router.post("/{trade_id}/resume", response_model=Dict[str, Any])
def resume_existing_trade(trade_id: str, db: Session = Depends(Database.get_db)):
    """Resume a paused trade"""
    trade = db.query(UserTrade).filter(UserTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with ID {trade_id} not found"
        )
    
    trade.status = UserTradeStatus.ACTIVE
    db.commit()
    db.refresh(trade)
    
    if trade.status != UserTradeStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade with ID {trade_id} could not be resumed. Current status: {trade.status.value}"
        )
    return {"trade_id": trade.id, "status": trade.status.value, "message": "Trade resumed successfully"}

@router.post("/{trade_id}/cancel", response_model=Dict[str, Any])
def cancel_existing_trade(trade_id: str, db: Session = Depends(Database.get_db)):
    """Cancel a trade"""
    trade = db.query(UserTrade).filter(UserTrade.id == trade_id).first()
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with ID {trade_id} not found"
        )
    
    trade.status = UserTradeStatus.STOPPED
    db.commit()
    db.refresh(trade)
    
    if trade.status != UserTradeStatus.STOPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade with ID {trade_id} could not be canceled. Current status: {trade.status.value}"
        )
    return {"trade_id": trade.id, "status": trade.status.value, "message": "Trade canceled successfully"}
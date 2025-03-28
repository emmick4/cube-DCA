from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from cube_dca.db.models import UserTrade, Order, UserTradeStatus, OrderStatus

def get_trade_info(db: Session, trade_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific trade
    """
    trade = db.query(UserTrade).filter(UserTrade.id == trade_id).first()
    if not trade:
        return None
    
    orders = db.query(Order).filter(Order.user_trade_id == trade_id).all()
    
    return {
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "total_quantity": trade.total_quantity,
        "limit_price": trade.limit_price,
        "strategy": trade.strategy,
        "status": trade.status.value,
        "created_at": trade.timestamp,
        "orders_count": len(orders),
        "orders": [get_order_info(order) for order in orders]
    }

def get_order_info(order: Order) -> Dict[str, Any]:
    """
    Get detailed information about an order
    """
    return {
        "order_id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "price": order.price,
        "quantity": order.quantity,
        "status": order.status.value,
        "created_at": datetime.fromtimestamp(order.created_at / 1_000_000_000) if order.created_at else None,
        "filled_at": datetime.fromtimestamp(order.filled_at / 1_000_000_000) if order.filled_at else None,
        "base_amount": order.base_amount,
        "quote_amount": order.quote_amount,
        "fee_amount": order.fee_amount
    }

def get_execution_stats(db: Session, trade_id: str) -> Dict[str, Any]:
    """
    Calculate execution statistics for a trade
    """
    trade = db.query(UserTrade).filter(UserTrade.id == trade_id).first()
    if not trade:
        return {"error": "Trade not found"}
    
    # Get all orders for this trade
    orders = db.query(Order).filter(Order.user_trade_id == trade_id).all()
    filled_orders = [o for o in orders if o.status == OrderStatus.FILLED]
    
    # Calculate execution statistics
    total_executed_quantity = sum(float(o.base_amount) if o.base_amount else 0 for o in filled_orders)
    total_executed_value = sum(float(o.quote_amount) if o.quote_amount else 0 for o in filled_orders)
    total_fees = sum(float(o.fee_amount) if o.fee_amount else 0 for o in filled_orders)
    
    # Calculate average execution price (VWAP)
    vwap = total_executed_value / total_executed_quantity if total_executed_quantity > 0 else 0
    
    # Calculate price improvement compared to limit price
    price_improvement = 0
    if trade.side.lower() == "buy":
        price_improvement = (trade.limit_price - vwap) / trade.limit_price * 100 if vwap > 0 else 0
    else:  # sell
        price_improvement = (vwap - trade.limit_price) / trade.limit_price * 100 if vwap > 0 else 0
    
    # Calculate execution time
    if filled_orders:
        first_order_time = min(datetime.fromtimestamp(o.created_at / 1_000_000_000) for o in filled_orders if o.created_at)
        last_fill_time = max(datetime.fromtimestamp(o.filled_at / 1_000_000_000) for o in filled_orders if o.filled_at)
        execution_time_seconds = (last_fill_time - first_order_time).total_seconds()
    else:
        execution_time_seconds = 0
    
    # Calculate execution progress
    execution_progress = (total_executed_quantity / trade.total_quantity * 100) if trade.total_quantity > 0 else 0
    
    # Order statistics
    orders_count = len(orders)
    filled_orders_count = len(filled_orders)
    open_orders_count = len([o for o in orders if o.status == OrderStatus.OPEN])
    canceled_orders_count = len([o for o in orders if o.status == OrderStatus.CANCELLED])
    rejected_orders_count = len([o for o in orders if o.status == OrderStatus.REJECTED])
    
    return {
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "strategy": trade.strategy,
        "status": trade.status.value,
        "total_target_quantity": trade.total_quantity,
        "total_executed_quantity": total_executed_quantity,
        "execution_progress": execution_progress,
        "average_execution_price": vwap,
        "limit_price": trade.limit_price,
        "price_improvement_percent": price_improvement,
        "total_execution_value": total_executed_value,
        "total_fees": total_fees,
        "execution_time_seconds": execution_time_seconds,
        "orders_statistics": {
            "total": orders_count,
            "filled": filled_orders_count,
            "open": open_orders_count,
            "canceled": canceled_orders_count,
            "rejected": rejected_orders_count,
            "fill_rate": filled_orders_count / orders_count * 100 if orders_count > 0 else 0
        }
    }

def get_all_trades_summary(db: Session) -> List[Dict[str, Any]]:
    """
    Get summary of all trades in the system
    """
    trades = db.query(UserTrade).all()
    
    result = []
    for trade in trades:
        orders = db.query(Order).filter(Order.user_trade_id == trade.id).all()
        filled_orders = [o for o in orders if o.status == OrderStatus.FILLED]
        
        total_executed_quantity = sum(float(o.base_amount) if o.base_amount else 0 for o in filled_orders)
        total_executed_value = sum(float(o.quote_amount) if o.quote_amount else 0 for o in filled_orders)
        
        vwap = total_executed_value / total_executed_quantity if total_executed_quantity > 0 else 0
        execution_progress = (total_executed_quantity / trade.total_quantity * 100) if trade.total_quantity > 0 else 0
        
        result.append({
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "strategy": trade.strategy,
            "status": trade.status.value,
            "created_at": trade.timestamp,
            "target_quantity": trade.total_quantity,
            "executed_quantity": total_executed_quantity,
            "progress": execution_progress,
            "avg_price": vwap,
            "limit_price": trade.limit_price,
            "orders_count": len(orders),
            "filled_orders_count": len(filled_orders)
        })
    
    return result
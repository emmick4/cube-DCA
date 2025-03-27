import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Enum, JSON, DateTime, Integer, BigInteger, Boolean
from sqlalchemy.orm import relationship
from .db import Base
from sqlalchemy.orm import DeclarativeBase
from cube.cube_types import OrderStatus


class Base(DeclarativeBase):
    pass


class UserTradeStatus(enum.Enum):
    PENDING = "pending" # waiting for the first order to be sent
    ACTIVE = "active" # trading
    PAUSED = "paused" # paused by user, waiting to be resumed
    STOPPED = "stopped" # stopped before completion, either by the user or by the system
    COMPLETED = "completed" # all orders have been sent and filled

class UserTrade(Base):
    __tablename__ = "user_trades"

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)  # BTCUSDC
    side = Column(String, nullable=False)    # "buy" or "sell"
    total_quantity = Column(Float, nullable=False)  # 1.2
    limit_price = Column(Float, nullable=False)  # Maximum price for buy orders, minimum price for sell orders
    strategy = Column(String, nullable=False)  # twap
    strategy_params = Column(JSON, nullable=False)  # {"frequency": 10, "total_duration": 1}
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(UserTradeStatus), nullable=False, default=UserTradeStatus.PENDING)

    # Relationship with orders
    orders = relationship("Order", back_populates="user_trade")

class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)  # orderId from exchange
    user_trade_id = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # Bid or Ask
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # New fields from exchange
    market_id = Column(Integer, nullable=False)
    created_at = Column(BigInteger, nullable=False)  # nanoseconds
    modified_at = Column(BigInteger, nullable=True)  # nanoseconds
    canceled_at = Column(BigInteger, nullable=True)  # nanoseconds
    filled_at = Column(BigInteger, nullable=True)  # nanoseconds
    reason = Column(String, nullable=True)  # reject/cancel reason
    settled = Column(Boolean, nullable=True)
    client_order_id = Column(BigInteger, nullable=True)
    time_in_force = Column(Integer, nullable=True)
    order_type = Column(Integer, nullable=True)
    self_trade_prevention = Column(Integer, nullable=True)
    cancel_on_disconnect = Column(Boolean, nullable=True)
    post_only = Column(Boolean, nullable=True)
    
    # Store arrays as JSON
    fills = Column(JSON, nullable=True)
    modifies = Column(JSON, nullable=True)
    order_fees = Column(JSON, nullable=True)
    
    # Filled total fields
    base_amount = Column(String, nullable=True)  # string number
    quote_amount = Column(String, nullable=True)  # string number
    fee_amount = Column(String, nullable=True)  # string number
    fee_asset_id = Column(Integer, nullable=True)  # int32
    filled_total_price = Column(BigInteger, nullable=True)  # int64
    filled_total_quantity = Column(BigInteger, nullable=True)  # int64

    # Relationship with UserTrade
    user_trade = relationship("UserTrade", back_populates="orders")

class OrderbookSnapshot(Base):
    __tablename__ = "orderbook_snapshots"

    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    bids = Column(JSON, nullable=False)  # List of [price, quantity] pairs
    asks = Column(JSON, nullable=False)  # List of [price, quantity] pairs


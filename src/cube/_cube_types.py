import enum
from typing import List, Optional
from dataclasses import dataclass

class OrderStatus(enum.Enum):
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

    def is_live(self) -> bool:
        return self in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]

@dataclass
class Market:
    market_id: int  # 100004
    symbol: str  # BTCUSDC
    base_asset_id: int  # 1
    base_lot_size: str  # 1000000000000000
    quote_asset_id: int  # 7
    quote_lot_size: int  # 1000000000000000
    price_display_decimals: int  # 1
    protection_price_levels: int  # 3000
    price_band_bid_pct: int  # 25
    price_band_ask_pct: int  # 25
    price_tick_size: str  # "0.1"
    quantity_tick_size: str  # "0.00001"
    fee_table_id: int  # 4
    status: int  # 1 or 2 is active, 3 is inactive
    display_rank: int = 1  # 1
    listed_at: str = ""  # "2023-10-29T00:00:00Z"
    is_primary: bool = True  # True


# class OrderbookLevel:
#     price: int
#     quantity: int
#     side: Side


# class Orderbook:
#     market: Market
#     bids: List[OrderbookLevel]
#     asks: List[OrderbookLevel]


# class FilledTotal:
#     base_amount: str
#     quote_amount: str
#     fee_amount: str
#     fee_asset_id: Optional[int] = None
#     filled_at: int
#     price: Optional[int] = None
#     quantity: Optional[int] = None


# class OrderModify:
#     price: int
#     quantity: int


# class OrderFee:
#     amount: str
#     asset_id: int


# class Order:
#     market: Market
#     side: str  # "Bid" or "Ask"
#     client_order_id: Optional[int] = None  # A unique order ID assigned by the client for this order
#     request_id: int  # A request ID that is echoed back on the NewOrderAck or NewOrderReject
#     market_id: int  # Market identifier
#     price: Optional[int] = None  # Optional price
#     quantity: Optional[int] = None  # Optional quantity, required for LIMIT orders
#     time_in_force: Optional[TimeInForce] = None
#     order_type: Optional[OrderType] = None
#     subaccount_id: int  # The subaccount to place this order on
#     self_trade_prevention: Optional[int] = None  # Optional self trade prevention setting
#     post_only: Optional[bool] = None  # Optional post only flag
#     cancel_on_disconnect: bool = False  # If true, order will be cancelled when connection closes
    
#     # Additional fields from spec
#     order_id: Optional[int] = None  # The cube-assigned order ID (ExchangeOrderId)
#     created_at: int  # Matching-engine transact-time in nanoseconds
#     modified_at: Optional[int] = None  # Transact-time of most recent modify event
#     canceled_at: Optional[int] = None  # Transact-time when order was cancelled
#     filled_at: Optional[int] = None  # Transact-time when order was filled
#     filled_total: Optional[FilledTotal] = None
#     fills: List['Fill'] = []
#     modifies: List[OrderModify] = []
#     reason: Optional[str] = None  # Reject reason if rejected, cancel reason if canceled
#     settled: Optional[bool] = None  # Settlement status for order's fills
#     status: OrderStatus
#     order_fees: List[OrderFee] = []


# class Fill:
#     """A fill for an order."""
#     msg_seq_num: Optional[int] = None
#     market_id: Optional[int] = None
#     client_order_id: Optional[int] = None  # The client order ID specified in the new-order request
#     exchange_order_id: Optional[int] = None  # Exchange order ID
#     fill_price: Optional[int] = None  # The price at which this trade occurred
#     fill_quantity: Optional[int] = None  # The quantity of the base asset that was traded in this fill
#     leaves_quantity: Optional[int] = None  # The remaining base quantity for this order after the fill is applied
#     fill_quote_quantity: Optional[int] = None  # The quantity of the quote asset that was traded in this fill
#     transact_time: Optional[int] = None  # Transact time
#     subaccount_id: Optional[int] = None
#     cumulative_quantity: Optional[int] = None  # The cumulative filled base quantity for this order after the fill is applied
#     side: Optional[str] = None  # Buy or sell
#     aggressor_indicator: Optional[bool] = None
#     fee_ratio: Optional[float] = None  # Indicates the fee charged on this trade
#     trade_id: Optional[int] = None  # The unique trade ID associated with a match event
    
#     # Additional fields from spec
#     settled: Optional[bool] = None  # Whether this fill has been settled
#     fee_amount: Optional[str] = None  # Fee amount for this fill
#     fee_asset_id: Optional[int] = None  # Asset ID for the fee

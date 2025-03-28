from cube.cube_client import CubeClient
from db.models import UserTrade, UserTradeStatus, Order
from datetime import datetime, timedelta
from services.market_manager import MarketManager
import time
import uuid
from db.db import Database

class TwapStrategy:
    name: str = "twap"
    description: str = "Trade a token pair for a time-weighted average price (TWAP)"

    def __init__(self, db_client: Database, cube_client: CubeClient, user_trade: UserTrade):
        self.db_client = db_client
        self.cube_client = cube_client
        self.user_trade = user_trade
        self.frequency = user_trade.strategy_params["frequency"]  # in seconds
        self.total_duration = user_trade.strategy_params["total_duration"]  # in hours
        self.start_time = user_trade.timestamp
        self.end_time = self.start_time + timedelta(hours=self.total_duration)
        self.remaining_quantity = user_trade.total_quantity
        self.last_order_time = None
        
        # Get market from MarketManager
        market_manager = MarketManager()
        self.market = market_manager.get_market(self.user_trade.symbol)
        if not self.market:
            raise ValueError(f"Market not found for symbol {self.user_trade.symbol}")
            
        # Validate and round initial parameters
        self.limit_price, _ = market_manager.validate_order(self.market, self.user_trade.limit_price, 0)
        _ , self.remaining_quantity = market_manager.validate_order(self.market, 0, self.remaining_quantity)

    def run(self, test_mode=-1):
        while True:
            # Check trade status
            if self.user_trade.status != UserTradeStatus.ACTIVE:
                self.pause()
                return

            current_time = datetime.utcnow()
            
            # Check if we've exceeded the total duration
            if current_time >= self.end_time:
                self.stop()
                return

            # Check if it's time to trade based on frequency
            if self.last_order_time is None or (current_time - self.last_order_time).total_seconds() >= self.frequency:
                # Get current market state
                balances = self.cube_client.get_balances()
                latest_orders = self.cube_client.get_latest_orders()
                
                # Cancel any existing orders
                for order in latest_orders:
                    if order.status in ["open", "partially_filled"]:
                        self.cube_client.cancel_order(order)

                # Get orderbook snapshot
                orderbook = self.cube_client.get_orderbook(self.market)

                # Calculate quantity for this interval
                remaining_intervals = (self.end_time - current_time).total_seconds() / self.frequency
                if remaining_intervals <= 0:
                    remaining_intervals = 1  # Ensure at least one interval for final trade
                
                interval_quantity = self.remaining_quantity / remaining_intervals

                # Validate and round order parameters
                market_manager = MarketManager()
                limit_price, interval_quantity = market_manager.validate_order(
                    self.market, 
                    self.limit_price, 
                    interval_quantity
                )
                if interval_quantity == 0:
                    self.stop()

                # Generate and submit order
                order = Order(
                    id=str(uuid.uuid4()),
                    user_trade_id=self.user_trade.id,
                    symbol=self.user_trade.symbol,
                    side=self.user_trade.side,
                    price=limit_price,
                    quantity=interval_quantity,
                    status="pending",
                    market=self.market,
                    created_at=int(current_time.timestamp() * 1e9),
                    time_in_force=1,  # GTC (Good Till Cancel)
                    order_type=1,  # LIMIT
                    post_only=True
                )
                self.db_client.add_order(order)

                # Submit order
                try:
                    self.cube_client.place_order(order)
                    self.last_order_time = current_time
                    self.remaining_quantity -= interval_quantity
                except Exception as e:
                    print(f"Error placing order: {e}")
                    # Continue to next iteration to retry

            # Sleep for a short period to prevent excessive CPU usage
            if test_mode == 0:
                return
            elif test_mode > 0:
                test_mode -= 1
            time.sleep(0.1)

    def pause(self):
        # Cancel all live orders for the market
        self.cube_client.cancel_market_orders(self.market)

    def stop(self):
        self.pause()
        self.user_trade.status = UserTradeStatus.COMPLETED
        self.db_client.update_user_trade(self.user_trade)

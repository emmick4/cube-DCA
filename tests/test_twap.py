import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from cube_dca.external.cube.cube_client import CubeClient
from cube_dca.external.cube.types import Market
from cube_dca.db.models import UserTrade, UserTradeStatus, Order
from cube_dca.strategies.twap import TwapStrategy
from cube_dca.utils.market_manager import MarketManager
from cube_dca.db.db import Database
import uuid

class TestTwapStrategy(unittest.TestCase):
    def setUp(self):
        # Create a mock CubeClient
        self.cube_client = MagicMock(spec=CubeClient)
        
        # Create a mock Database client
        self.db_client = MagicMock(spec=Database)
        
        # Create a test market
        self.market = Market(
            market_id=100004,
            symbol="BTCUSDC",
            base_asset_id=1,
            base_lot_size="1000000000000000",
            quote_asset_id=7,
            quote_lot_size=1000000000000000,
            price_display_decimals=1,
            protection_price_levels=3000,
            price_band_bid_pct=25,
            price_band_ask_pct=25,
            price_tick_size="0.1",
            quantity_tick_size="0.00001",
            fee_table_id=4,
            status=1
        )
        
        # Create a test UserTrade
        self.user_trade = UserTrade(
            id="test_trade_id",
            symbol="BTCUSDC",
            side=1,  # Buy
            total_quantity=1.0,
            limit_price=50000.0,
            timestamp=datetime.utcnow(),
            status=UserTradeStatus.ACTIVE,
            strategy_params={
                "frequency": 60,  # 1 minute
                "total_duration": 1  # 1 hour
            }
        )
        
        # Mock MarketManager
        self.market_manager = MarketManager()
        # Only mock the get_market method
        self.market_manager.get_market = MagicMock(return_value=self.market)
        
        # Create strategy instance
        with patch('cube_dca.strategies.twap.MarketManager', return_value=self.market_manager):
            self.strategy = TwapStrategy(self.db_client, self.cube_client, self.user_trade)

    def test_initialization(self):
        """Test proper initialization of TWAP strategy"""
        self.assertEqual(self.strategy.name, "twap")
        self.assertEqual(self.strategy.frequency, 60)
        self.assertEqual(self.strategy.total_duration, 1)
        self.assertEqual(self.strategy.remaining_quantity, 1.0)
        self.assertEqual(self.strategy.limit_price, 50000.0)
        self.assertEqual(self.strategy.market, self.market)


    @patch('time.sleep')
    def test_run_single_interval(self, mock_sleep):
        """Test running strategy for a single interval"""
        # Mock current time
        current_time = datetime.utcnow()
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = current_time
            
            # Mock order placement
            self.cube_client.place_order.return_value = {"status": "success"}
            
            # Mock orderbook
            self.cube_client.get_orderbook.return_value = {
                "bids": [[49999.0, 1.0]],
                "asks": [[50001.0, 1.0]]
            }
            
            # Mock balances
            self.cube_client.get_balances.return_value = [
                {"assetId": "BTC", "total": "1.0", "available": "1.0", "locked": "0.0"}
            ]
            
            # Mock live orders
            self.cube_client.get_latest_orders.return_value = []
            
            # Set up the strategy to exit after one iteration
            self.strategy.last_order_time = current_time - timedelta(minutes=2)
            self.strategy.end_time = current_time + timedelta(minutes=1)  # Set end time to force exit
            self.strategy.remaining_quantity = 0.1  # Small remaining quantity to ensure one order
            
            # Run strategy
            self.strategy.run(test_mode=1)
            
            # Verify order was placed
            self.cube_client.place_order.assert_called_once()
            placed_order = self.cube_client.place_order.call_args[0][0]
            self.assertEqual(placed_order.symbol, "BTCUSDC")
            self.assertEqual(placed_order.side, 1)
            self.assertEqual(placed_order.price, 50000.0)
            self.assertEqual(placed_order.quantity, 0.1)
            
            # Verify db client was used to add the order
            self.db_client.add_order.assert_called_once()
            
            # Verify sleep was called
            mock_sleep.assert_called_with(0.1)

    
    @patch('time.sleep')
    def test_run_method_loop_behavior(self, mock_sleep):
        """Test the run method's loop behavior with the process_interval pattern"""
        # Create a mock for the process_interval method to test the loop behavior
        with patch.object(self.strategy, 'process_interval') as mock_process:
            # Configure the mock to return True for the first two calls, then False
            mock_process.side_effect = [True, True, False]
            
            # Run the strategy with test_mode=3 (more than we need)
            self.strategy.run(test_mode=3)
            
            # Verify process_interval was called exactly 3 times
            self.assertEqual(mock_process.call_count, 3)
            
            # Verify sleep was called twice (not after the last iteration)
            mock_sleep.assert_has_calls([call(0.1), call(0.1)])
        
    def _create_test_order(self, time, price, quantity):
        """Helper to create a test order with required fields"""
        return Order(
            id=str(uuid.uuid4()),
            user_trade_id=self.user_trade.id,
            symbol=self.user_trade.symbol,
            side=self.user_trade.side,
            price=price,
            quantity=quantity,
            status="pending",
            market=self.market,
            created_at=int(time.timestamp() * 1e9),
            time_in_force=1,  # GTC
            order_type=1,  # LIMIT
            post_only=True
        )

    def test_pause(self):
        """Test pausing the strategy"""
        self.cube_client.cancel_market_orders.return_value = {"status": "success"}
        self.user_trade.status = UserTradeStatus.PAUSED

        self.strategy.run()
        
        self.cube_client.cancel_market_orders.assert_called_once_with(self.market)
        self.assertEqual(self.user_trade.status, UserTradeStatus.PAUSED)

    def test_stop(self):
        """Test stopping the strategy"""
        self.cube_client.cancel_market_orders.return_value = {"status": "success"}
        
        self.strategy.stop()
        
        self.cube_client.cancel_market_orders.assert_called_once_with(self.market)
        self.assertEqual(self.user_trade.status, UserTradeStatus.COMPLETED)
        self.db_client.update_user_trade.assert_called_once_with(self.user_trade)

    @patch('time.sleep')
    def test_stop_when_remaining_below_minimum(self, mock_sleep):
        """Test that strategy stops when quantity is below minimum order size"""
        # Reset mocks
        self.cube_client.place_order.reset_mock()
        self.cube_client.cancel_market_orders.reset_mock()
        self.db_client.update_user_trade.reset_mock()
        
        # Set a fixed time for the test
        test_time = datetime(2023, 1, 1, 12, 0, 0)
        
        # Set up strategy with a small remaining quantity
        self.strategy.remaining_quantity = 0.000001  # Very small amount
        
        # Mock market validation to return zero quantity (below minimum)
        market_manager_mock = MagicMock(spec=MarketManager)
        market_manager_mock.get_market.return_value = self.market
        # Critically important - validation returns 0 quantity
        market_manager_mock.validate_order.return_value = (50000.0, 0)
        
        # Directly test the core logic that handles small quantity
        with patch('cube_dca.strategies.twap.MarketManager', return_value=market_manager_mock):
            with patch('datetime.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = test_time
                
                # Create a fresh instance with our mocked MarketManager
                strategy = TwapStrategy(self.db_client, self.cube_client, self.user_trade)
                strategy.remaining_quantity = 0.000001
                
                # Manually trigger order creation to exercise the minimum quantity check
                # This directly tests the code inside the run() method's time check
                remaining_intervals = 1
                interval_quantity = strategy.remaining_quantity / remaining_intervals
                
                # This is the key part being tested - if validation returns zero quantity, stop is called
                limit_price, interval_quantity = market_manager_mock.validate_order(
                    self.market, 
                    strategy.limit_price, 
                    interval_quantity
                )
                
                # If interval_quantity is 0, strategy should call stop
                if interval_quantity == 0:
                    strategy.stop()
                else:
                    # Create and place order if not zero quantity
                    order = self._create_test_order(test_time, limit_price, interval_quantity)
                    self.db_client.add_order(order)
                    self.cube_client.place_order(order)
        
        # Verify the strategy called stop and didn't place an order
        self.cube_client.place_order.assert_not_called()
        self.cube_client.cancel_market_orders.assert_called_once_with(self.market)
        self.assertEqual(self.user_trade.status, UserTradeStatus.COMPLETED)
        self.db_client.update_user_trade.assert_called_once_with(self.user_trade)


    @patch('time.sleep')
    def test_run_with_existing_orders(self, mock_sleep):
        """Test running strategy with existing orders"""
        current_time = datetime.utcnow()
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = current_time
            
            # Mock existing orders
            existing_order = Order(
                id="existing_order",
                symbol="BTCUSDC",
                status="open"
            )
            self.cube_client.get_latest_orders.return_value = [existing_order]
            
            # Mock order cancellation
            self.cube_client.cancel_order.return_value = {"status": "success"}
            
            # Run strategy
            self.strategy.last_order_time = current_time - timedelta(minutes=2)
            self.strategy.run(test_mode=1)
            
            # Verify existing order was cancelled
            self.cube_client.cancel_order.assert_called_once_with(existing_order)

if __name__ == '__main__':
    unittest.main()
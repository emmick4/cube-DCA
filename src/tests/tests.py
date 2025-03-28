import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import base64
import time

from cube.cube_client import CubeClient, generate_signature
from cube._cube_types import Market
from db.models import Order
from db.models import UserTrade

class TestCubeClient(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key"
        # Use a base64-encoded test secret
        self.api_secret = "dGVzdF9zZWNyZXRfZm9yX3Rlc3Rpbmc="  # base64 encoded "test_secret_for_testing"
        self.subaccount_id = 1
        self.client = CubeClient(self.api_key, self.api_secret, self.subaccount_id)
        
        # Create a common Market instance for all tests
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

    def test_generate_signature(self):
        """Test signature generation for API authentication"""
        signature, timestamp = generate_signature(self.api_secret)
        
        # Verify signature is a valid base64 string
        self.assertIsInstance(signature, str)
        self.assertTrue(len(signature) > 0)
        try:
            # Verify it's valid base64
            base64.b64decode(signature)
        except Exception as e:
            self.fail(f"Signature is not valid base64: {e}")

    @patch('httpx.request')
    def test_get_latest_orders(self, mock_request):
        """Test fetching latest orders"""
        # Mock response data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "orderId": "123",
            "clientOrderId": "client123",
            "marketId": 100004,
            "side": 1,
            "price": "50000.0",
            "qty": "0.1",
            "status": "filled",
            "createdAt": 1679000000000000000,
            "filledAt": 1679000001000000000,
            "fills": [{"price": "50000.0", "qty": "0.1"}],
            "orderFees": [{"amount": "0.0001", "assetId": "BTC"}]
        }]
        mock_request.return_value = mock_response

        orders = self.client.get_latest_orders()
        
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].id, "123")
        self.assertEqual(orders[0].symbol, "BTCUSDC")
        self.assertEqual(orders[0].price, 50000.0)
        self.assertEqual(orders[0].quantity, 0.1)
        self.assertEqual(orders[0].status, "filled")

    @patch('httpx.request')
    def test_place_order(self, mock_request):
        """Test placing a new order"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        order = Order(
            client_order_id="test123",
            market=self.market,
            price=50000.0,
            quantity=0.1,
            side=1,
            time_in_force=1,
            order_type=1,
            self_trade_prevention=1,
            post_only=False,
            cancel_on_disconnect=False
        )

        result = self.client.place_order(order)
        self.assertEqual(result["status"], "success")

    @patch('httpx.request')
    def test_cancel_order(self, mock_request):
        """Test canceling an order"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        order = Order(
            client_order_id="test123",
            market=self.market,
            price=50000.0,
            quantity=0.1,
            side=1,
            time_in_force=1,
            order_type=1,
            self_trade_prevention=1,
            post_only=False,
            cancel_on_disconnect=False
        )

        result = self.client.cancel_order(order)
        self.assertEqual(result["status"], "success")

    @patch('httpx.request')
    def test_get_balances(self, mock_request):
        """Test fetching account balances"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "assetId": "BTC",
                "total": "1.0",
                "available": "0.8",
                "locked": "0.2"
            }
        ]
        mock_request.return_value = mock_response

        balances = self.client.get_balances()
        self.assertEqual(len(balances), 1)
        self.assertEqual(balances[0]["assetId"], "BTC")
        self.assertEqual(balances[0]["total"], "1.0")

    @patch('httpx.request')
    def test_get_orderbook(self, mock_request):
        """Test fetching orderbook"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bids": [[50000.0, 1.0], [49999.0, 2.0]],
            "asks": [[50001.0, 1.0], [50002.0, 2.0]]
        }
        mock_request.return_value = mock_response

        orderbook = self.client.get_orderbook(self.market)
        
        self.assertIn("bids", orderbook)
        self.assertIn("asks", orderbook)
        self.assertEqual(len(orderbook["bids"]), 2)
        self.assertEqual(len(orderbook["asks"]), 2)

    @patch('httpx.request')
    def test_error_handling(self, mock_request):
        """Test error handling and retries"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response

        # Test with retries
        with self.assertRaises(Exception):
            self.client.get_latest_orders()
        # Verify that we attempted the correct number of retries
        # The initial request + 1 retry = 2 total calls
        self.assertEqual(mock_request.call_count, 2)
        
        # Reset the mock for the next test
        mock_request.reset_mock()

        # Test without retries
        with self.assertRaises(Exception):
            self.client.check_api_key()

if __name__ == '__main__':
    unittest.main()

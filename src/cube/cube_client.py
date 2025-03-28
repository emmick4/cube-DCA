import random
import logging
import time
import base64
import hmac
import hashlib
import httpx
from datetime import datetime

from db.models import Order
from cube._cube_types import Market
from services.market_manager import MarketManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.cube.exchange/os/v0"

def generate_signature(api_secret: str) -> tuple[str, int]:
    """
    Generate the API signature and timestamp for Cube API authentication.
    Returns a tuple of (signature, timestamp).
    """
    # Get current timestamp
    timestamp = int(time.time())
    
    # Convert timestamp to 8-byte little-endian array
    timestamp_bytes = timestamp.to_bytes(8, byteorder='little')
    
    # Create payload: "cube.xyz" + timestamp_bytes
    payload = b"cube.xyz" + timestamp_bytes
    
    # Decode base64 secret key to bytes
    secret_bytes = base64.b64decode(api_secret)
    
    # Calculate HMAC-SHA256
    hmac_obj = hmac.new(secret_bytes, payload, hashlib.sha256)
    signature = hmac_obj.digest()
    
    # Base64 encode the signature
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    
    return signature_b64, timestamp

class CubeClient:
    def __init__(self, api_key: str, api_secret: str, subaccount_id: int = 1):
        self.api_key = api_key
        self.api_secret = api_secret
        self.subaccount_id = subaccount_id
        self.market_manager = MarketManager()

    def _make_request(self, method: str, path: str, params: dict = None, data: dict = None, retries: int = 1):
        url = f"{BASE_URL}{path}"
        
        # Generate signature and timestamp
        signature, timestamp = generate_signature(self.api_secret)
        
        headers = {
            "x-api-key": f"{self.api_key}",
            "x-api-signature": signature,
            "x-api-timestamp": str(timestamp)
        }
        response = httpx.request(method, url, headers=headers, params=params, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Request failed with status {response.status_code}: {response.text}")
            if retries > 0:
                logger.info("Retrying request...")
                return self._make_request(method, path, params, data, retries=retries-1)
            raise Exception(f"Request failed with status {response.status_code}: {response.text}")

    def get_latest_orders(self, limit: int = 500):
        path = f"/users/subaccount/{self.subaccount_id}/orders"
        result = self._make_request("GET", path, params={"limit": limit}, retries=1)
        orders = []
        
        for order_data in result:
            # Get market information from MarketManager
            market_id = order_data.get("marketId")
            market = next((m for m in self.market_manager.get_all_markets().values() if m.market_id == market_id), None)
            if not market:
                logger.warning(f"Market not found for market_id {market_id}")
                continue
                
            # Convert the order data to match our ORM model
            order_dict = {
                "id": str(order_data.get("orderId")),  # Convert to string for primary key
                "user_trade_id": str(order_data.get("clientOrderId")),  # Using clientOrderId as user_trade_id
                "symbol": market.symbol,  # Use symbol from MarketManager
                "side": order_data.get("side"),
                "price": float(order_data.get("price", 0)),
                "quantity": float(order_data.get("qty", 0)),
                "status": order_data.get("status", "open"),
                "timestamp": datetime.fromtimestamp(order_data.get("createdAt", 0) / 1e9),  # Convert nanoseconds to datetime
                
                # New fields from exchange
                "market_id": order_data.get("marketId"),
                "created_at": order_data.get("createdAt"),
                "modified_at": order_data.get("modifiedAt"),
                "canceled_at": order_data.get("canceledAt"),
                "filled_at": order_data.get("filledAt"),
                "reason": order_data.get("reason"),
                "settled": order_data.get("settled"),
                "client_order_id": order_data.get("clientOrderId"),
                "time_in_force": order_data.get("timeInForce"),
                "order_type": order_data.get("orderType"),
                "self_trade_prevention": order_data.get("selfTradePrevention"),
                "cancel_on_disconnect": order_data.get("cancelOnDisconnect"),
                "post_only": order_data.get("postOnly"),
                
                # Store arrays as JSON
                "fills": order_data.get("fills", []),
                "modifies": order_data.get("modifies", []),
                "order_fees": order_data.get("orderFees", []),
            }
            
            # Handle filled total data if present
            if filled_total := order_data.get("filledTotal"):
                order_dict.update({
                    "base_amount": filled_total.get("baseAmount"),
                    "quote_amount": filled_total.get("quoteAmount"),
                    "fee_amount": filled_total.get("feeAmount"),
                    "fee_asset_id": filled_total.get("feeAssetId"),
                    "filled_total_price": filled_total.get("price"),
                    "filled_total_quantity": filled_total.get("quantity"),
                })
            
            orders.append(Order(**order_dict))
        
        return orders
    
    # def get_live_orders(self):
    #     path = f"/orders"
    #     return self._make_request("GET", path, params={"subaccountId": self.subaccount_id})

    def cancel_market_orders(self, market: Market):
        path = "/orders"
        return self._make_request("DELETE", path, data={
            "subaccountId": self.subaccount_id,
            "requestId": random.getrandbits(64),
            "marketId": market.market_id,
            },
            retries=3)
    
    def cancel_order(self, order: Order):
        path = "/order"
        return self._make_request("DELETE", path, data={
            "subaccountId": self.subaccount_id,
            "requestId": random.getrandbits(64),
            "clientOrderId": order.client_order_id,
            "marketId": order.market_id
        })
    
    def place_order(self, order: Order):
        path = "/order"
        return self._make_request("POST", path, data={
            "clientOrderId": order.client_order_id,
            "requestId": random.getrandbits(64),
            "marketId": order.market_id,
            "price": order.price,
            "quantity": order.quantity,
            "side": int(order.side),
            "timeInForce": int(order.time_in_force),
            "orderType": int(order.order_type),
            "subaccountId": self.subaccount_id,
            "selfTradePrevention": int(order.self_trade_prevention),
            "postOnly": order.post_only,
            "cancelOnDisconnect": order.cancel_on_disconnect,
        })
    
    def get_balances(self):
        path = "/positions"
        return self._make_request("GET", path, params={"subaccountId": self.subaccount_id})
    
    def get_orderbook(self, market: Market, depth: int = 1000):
        path = f"/parsed/book/{market.symbol}/snapshot"
        return self._make_request("GET", path, params={"depth": depth})

    def check_api_key(self):
        path = "/users/check"
        return self._make_request("GET", path, retries=0)

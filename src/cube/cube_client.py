import random
import logging
import time
import base64
import hmac
import hashlib
from cube_types import Market, Side, Order
import xhttp

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
    
    # Decode hex secret key to bytes
    secret_bytes = bytes.fromhex(api_secret)
    
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

    def _make_request(self, method: str, path: str, params: dict = None, data: dict = None, retries: int = 1):
        url = f"{BASE_URL}{path}"
        
        # Generate signature and timestamp
        signature, timestamp = generate_signature(self.api_secret)
        
        headers = {
            "x-api-key": f"{self.api_key}",
            "x-api-signature": signature,
            "x-api-timestamp": str(timestamp)
        }
        response = xhttp.request(method, url, headers=headers, params=params, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Request failed with status {response.status_code}: {response.text}")
            if retries > 0:
                logger.info("Retrying request...")
                return self._make_request(method, path, params, data, retries=retries-1)
            return None

    def get_latest_orders(self, limit: int = 500):
        path = f"/users/subaccount/{self.subaccount_id}/orders"
        result = self._make_request("GET", path, params={"limit": limit})
        
        return [Order(**order) for order in result]
    
    def get_live_orders(self):
        path = f"/orders"
        return self._make_request("GET", path, params={"subaccountId": self.subaccount_id})

    def cancel_market_orders(self, market: Market):
        path = "/orders"
        return self._make_request("DELETE", path, data={
            "subaccountId": self.subaccount_id,
            "requestId": random.randint(),
            "marketId": market.market_id,
            },
            retries=3)
    
    def cancel_order(self, order: Order):
        path = "/order"
        return self._make_request("DELETE", path, data={
            "subaccountId": self.subaccount_id,
            "requestId": random.randint(),
            "clientOrderId": order.client_order_id,
            "marketId": order.market.market_id
        })
    
    def place_order(self, order: Order):
        path = "/order"
        return self._make_request("POST", path, data={
            "clientOrderId": order.client_order_id,
            "requestId": random.randint(),
            "marketId": order.market.market_id,
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
        path = f"/parsed/book/{market.market_symbol}/snapshot"
        return self._make_request("GET", path, params={"depth": depth})

    def check_api_key(self):
        path = "/users/check"
        return self._make_request("GET", path, retries=0)

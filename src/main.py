from db.db import Database
from cube.cube_client import CubeClient
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
import threading

class TradeManager:
    def __init__(self, max_workers: int = 10):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_trades: Dict[str, threading.Thread] = {}  # trade_id -> thread
        self.lock = threading.Lock()

    def start_trade(self, trade) -> None:
        with self.lock:
            if trade.id not in self.active_trades:
                future = self.executor.submit(trade.run)
                self.active_trades[trade.id] = future

    def stop_trade(self, trade_id: str) -> None:
        with self.lock:
            if trade_id in self.active_trades:
                future = self.active_trades[trade_id]
                future.cancel()
                del self.active_trades[trade_id]

    def cleanup_completed_trades(self) -> None:
        with self.lock:
            completed_trades = [
                trade_id for trade_id, future in self.active_trades.items()
                if future.done()
            ]
            for trade_id in completed_trades:
                del self.active_trades[trade_id]

    def is_trade_active(self, trade_id: str) -> bool:
        with self.lock:
            return trade_id in self.active_trades and not self.active_trades[trade_id].done()

def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    db = Database(config["db"]["url"])
    
    cube_client = CubeClient(
        api_key=config["cube"]["api_key"],
        api_secret=config["cube"]["api_secret"],
        subaccount_id=config["cube"]["subaccount_id"]
    )
    cube_client.check_api_key()

    # Initialize trade manager
    trade_manager = TradeManager()

    # spin up active trade threads
    trades = db.get_active_trades()
    for trade in trades:
        trade_manager.start_trade(trade)

    while True:
        # Update order states
        db_orders = db.get_live_orders()  # list of Order objects
        cube_orders = {order["clientOrderId"]: order for order in cube_client.get_latest_orders()}  # dict of clientOrderId -> Order
        for db_order in db_orders:
            cube_order = cube_orders[db_order.client_order_id]
            # update db state
            db.update_order(cube_order)
        
        # Clean up completed trades
        trade_manager.cleanup_completed_trades()
        
        # Check for trades that need to be started
        current_trades = db.get_active_trades()
        for trade in current_trades:
            if not trade_manager.is_trade_active(trade.id):
                trade_manager.start_trade(trade)

if __name__ == "__main__":
    main()

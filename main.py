from cube_dca.db.db import Database
from cube_dca.external.cube.cube_client import CubeClient
from cube_dca.core.trade_manager import TradeManager
import json

def main():
    with open("config/config.json", "r") as f:
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

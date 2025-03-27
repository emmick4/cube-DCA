import httpx
import websockets
from db import Database
from cube.cube_client import CubeClient
from cube.cube_types import OrderStatus
import json
import logging

def main():
    with open("config.json", "r") as f:
        config = json.load(f)

    db = Database()
    
    cube_client = CubeClient(
        api_key=config["cube"]["api_key"],
        api_secret=config["cube"]["api_secret"],
        subaccount_id=config["cube"]["subaccount_id"]
    )
    cube_client.check_api_key()


    # spin up active trade threads
    trades = db.get_active_trades()
    for trade in trades:
        trade_thread = threading.Thread(target=trade.run)
        trade_thread.start()

    while True:
        db_orders = db.get_live_orders() # list of Order objects
        cube_orders = {order["clientOrderId"]: order for order in cube_client.get_latest_orders()} # dict of clientOrderId -> Order
        for db_order in db_orders:
            cube_order = cube_orders[db_order.client_order_id]
            
            
            

    # main loop
    # update db state for live orders

    # check for live trades that don't have a thread and spin up new threads for them
    pass

if __name__ == "__main__":
    main()

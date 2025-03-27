from cube import CubeClient
from cube import cube_types
from db.models import UserTrade, UserTradeStatus

class TwapStrategy:
    name: str = "twap"
    description: str = "Trade a token pair for a time-weighted average price (TWAP)"

    def __init__(self, cube_client: CubeClient, user_trade: UserTrade):
        self.cube_client = cube_client
        self.user_trade = user_trade
        self.frequency = user_trade.strategy_params["frequency"]
        self.total_duration = user_trade.strategy_params["total_duration"]

    def run(self):
        # loop until the trade is stopped
        # get trade status from db
        # if it's not active, return. the main loop will take care of spinning up a new thread if the trade is activated

        # if it's time to trade:
        # get current balances, living orders, latest orders from client

        # make sure it's time to trade based on the frequency, total duration, and latest orders we've sent
        # cancel any living orders
        # get orderbook snapshot

        # calculate how much to trade

        # generate pending order(s)
        # add pending orders to db

        # submit orders
        pass

    def pause(self):
        # cancel all living orders
        pass

    def stop(self):
        self.pause()
        self.user_trade.status = UserTradeStatus.COMPLETED
        self.user_trade.save()

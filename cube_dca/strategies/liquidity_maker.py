from cube_dca.external.cube.cube_client import CubeClient
from cube_dca.db.models import UserTrade, UserTradeStatus

class LiquidityMakerStrategy:
    name: str = "liquidity_maker"
    description: str = "Make directional liquidity for a given token pair"

    def __init__(self, cube_client: CubeClient, user_trade: UserTrade):
        self.cube_client = cube_client
        self.user_trade = user_trade
        self.depth = user_trade.strategy_params["depth"] # how far out to make liquidity
        self.distribution = user_trade.strategy_params["distribution"] # params for the curve of the distribution

    def run(self):
        # loop until the trade is stopped
        # get trade status from db
        # if it's not active, return. the main loop will take care of spinning up a new thread if the trade is activated

        # get current balances, living orders, latest orders, orderbook snapshot from client

        # see if it's time to trade based on the orderbook snapshot, our living orders, and the depth and distribution parameters

        # generate pending order(s) attempting to leave our living orders in the orderbook to maintain their place in the execution queue,
        # but cancelling any that are outside the depth or far enough outside the distribution parameters

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

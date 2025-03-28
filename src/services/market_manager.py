from cube._cube_types import Market
import json
import os
from typing import Dict, Optional
from decimal import Decimal, ROUND_DOWN

class MarketManager:
    _instance = None
    _markets: Dict[str, Market] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MarketManager, cls).__new__(cls)
            cls._instance._load_markets()
        return cls._instance
    
    def _load_markets(self):
        """Load all markets from markets.json"""
        markets_file = os.path.join(os.path.dirname(__file__), '..', 'markets.json')
        with open(markets_file, 'r') as f:
            markets_data = json.load(f)
            
        for market_data in markets_data['result']['markets']:
            try:
                market = Market(
                    market_id=market_data['marketId'],
                    symbol=market_data['symbol'],
                    base_asset_id=market_data['baseAssetId'],
                    base_lot_size=market_data['baseLotSize'],
                    quote_asset_id=market_data['quoteAssetId'],
                    quote_lot_size=market_data['quoteLotSize'],
                    price_display_decimals=market_data['priceDisplayDecimals'],
                    protection_price_levels=market_data['protectionPriceLevels'],
                    price_band_bid_pct=market_data.get('priceBandBidPct', 100),
                    price_band_ask_pct=market_data.get('priceBandAskPct', 100),
                    price_tick_size=market_data['priceTickSize'],
                    quantity_tick_size=market_data['quantityTickSize'],
                    fee_table_id=market_data['feeTableId'],
                    status=market_data['status'],
                    display_rank=market_data.get('displayRank', 0),
                    listed_at=market_data['listedAt'],
                    is_primary=market_data.get('isPrimary', False)
                )
            except Exception as e:
                print(f"Error loading market {market_data['symbol']}: {e}\n\n{market_data}")
                raise e
            
            self._markets[market.symbol] = market
    
    def get_market(self, symbol: str) -> Optional[Market]:
        """Get a market by its symbol"""
        return self._markets.get(symbol)
    
    def get_all_markets(self) -> Dict[str, Market]:
        """Get all markets"""
        return self._markets.copy()
        
    def round_price(self, market: Market, price: float) -> float:
        """Round price according to market's price tick size"""
        tick_size = Decimal(str(market.price_tick_size))
        price_decimal = Decimal(str(price))
        # Round down to nearest tick size
        rounded = (price_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        return float(rounded)
        
    def round_quantity(self, market: Market, quantity: float) -> float:
        """Round quantity according to market's quantity tick size"""
        tick_size = Decimal(str(market.quantity_tick_size))
        quantity_decimal = Decimal(str(quantity))
        # Round down to nearest tick size
        rounded = (quantity_decimal / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
        return float(rounded)
        
    def validate_order(self, market: Market, price: float, quantity: float) -> tuple[float, float]:
        """Validate and round both price and quantity according to market requirements"""
        rounded_price = self.round_price(market, price)
        rounded_quantity = self.round_quantity(market, quantity)
        return rounded_price, rounded_quantity 
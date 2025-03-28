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
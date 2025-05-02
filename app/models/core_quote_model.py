from dataclasses import dataclass
from datetime import datetime

@dataclass
class CoreQuoteModel:
    symbol: str
    last_price: float
    bid: float
    ask: float
    open_price: float
    high: float
    low: float
    prev_close: float
    volume: int
    average_volume_10_day: float
    timestamp: datetime
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass
class OptionContract:
    contract_symbol: str
    strike_price: float
    type: str
    bid: float
    ask: float
    last: float
    open_interest: int
    volume: int
    implied_volatility: float
    delta: float
    gamma: float
    theta: float
    vega: float

@dataclass
class OptionChainSnapshot:
    expiration_date: datetime
    options: List[OptionContract]
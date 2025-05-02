from dataclasses import dataclass
from datetime import datetime

@dataclass
class FundamentalsModel:
    earnings_date: datetime
    next_Dividend_date: datetime
    dividend_yield: float
    beta: float
    market_cap: float
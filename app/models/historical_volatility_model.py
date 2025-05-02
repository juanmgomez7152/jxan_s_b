from dataclasses import dataclass
from datetime import datetime

@dataclass
class HistoicalPrice:
    date: datetime
    close: float
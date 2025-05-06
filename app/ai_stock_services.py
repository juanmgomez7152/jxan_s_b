# from cachetools import TTLCache
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import re
import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)

load_dotenv()
MODEL_NAME = "gpt-4.1"
client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")

class Earnings(BaseModel):
    nextEarningsDate: str
    lastEarningsDate: str
    estimatedEarnings: float
    actualEarnings: float
    earningsSurprisePercent: float
class Dividends(BaseModel):
    nextDividendDate: str
    dividendAmount: float
    dividendYield: float
class Events(BaseModel):
    type: str
    description: str
    date: str
class Fundementals(BaseModel):
    earnings: Earnings
    dividends: Dividends
    events: list[Events]

async def get_ai_stock_recommendations(ticker):
    pass

async def get_ai_stock_news(ticker):
    pass

async def macro_stock_options_analysis(payload):
    try:
        responses = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0,
            top_p=1,
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are a Stock Options Portfolio Agent.

                    Your goal is to select the best combination of weekly options trades (2 to 14 day hold) within the given budget to maximize profit.

                    PAYLOAD:
                    {
                    "List of Best Trades": [ … ],
                    "availableCash": float
                    }

                    REQUIREMENTS:
                    - Use only the data in the payload; do not hallucinate.
                    - Calculate `contractsToBuy` = floor(availableCashRemaining / (100 * premiumPerContract)).
                    - Pack as many contracts of each trade as your budget allows, prioritizing higher `score`.
                    - Do NOT output ANY explanatory text or markdown—**output ONLY** the final JSON object.
                    
                    EXAMPLE:
                    *****
                    Here is the payload:
                    Example 1 (fit two small trades)
                    Here is the payload:
                    {
                        "List of Best Trades": [
                            { "symbol":"AAPL", "bestTrade":{ "contractSymbol":"AAPL250509P00195000","type":"PUT","strikePrice":195.0,"expirationDate":"2025-05-09T20:00:00.000+00:00","premiumPerContract":1.50,"exitPremium":2.00 }, "score":7.5 },
                            { "symbol":"TSLA", "bestTrade":{ "contractSymbol":"TSLA250516C00800000","type":"CALL","strikePrice":800.0,"expirationDate":"2025-05-16T20:00:00.000+00:00","premiumPerContract":2.00,"exitPremium":3.10 }, "score":8.0 },
                            { "symbol":"MSFT", "bestTrade":{ "contractSymbol":"MSFT250516C00440000","type":"CALL","strikePrice":440.0,"expirationDate":"2025-05-16T20:00:00.000+00:00","premiumPerContract":6.85,"exitPremium":9.15 }, "score":8.2 }
                        ],
                        "availableCash": 1000.00
                    }
                    OUTPUT:
                    {
                        "selectedTrades": [
                            {
                            "symbol": "MSFT",
                            "contractSymbol": "MSFT250516C00440000",
                            "type": "CALL",
                            "strikePrice": 440.0,
                            "expirationDate": "2025-05-16",
                            "premiumPerContract": 6.85,
                            "exitPremium": 9.15,
                            "score": 8.2,
                            "contractsToBuy": 1
                            },
                            {
                            "symbol": "TSLA",
                            "contractSymbol": "TSLA250516C00800000",
                            "type": "CALL",
                            "strikePrice": 800.0,
                            "expirationDate": "2025-05-16",
                            "premiumPerContract": 2.00,
                            "exitPremium": 3.10,
                            "score": 8.0,
                            "contractsToBuy": 1
                            }
                        ],
                        "totalPremiumUsed": 885.00
                    }
                    ******
                    Example 2 (only one big-ticket trade fits)
                    Here is the payload:
                    {
                        "List of Best Trades": [
                            { "symbol":"NFLX", "bestTrade":{ "contractSymbol":"NFLX250509C00500000","type":"CALL","strikePrice":500.0,"expirationDate":"2025-05-09T20:00:00.000+00:00","premiumPerContract":8.00,"exitPremium":10.00 }, "score":8.5 },
                            { "symbol":"AMD",  "bestTrade":{ "contractSymbol":"AMD250516P00090000","type":"PUT","strikePrice":90.0, "expirationDate":"2025-05-16T20:00:00.000+00:00","premiumPerContract":0.80,"exitPremium":1.20 }, "score":7.0 }
                        ],
                        "availableCash": 500.0
                    }
                    OUTPUT:
                    {
                    "selectedTrades": [
                        {
                        "symbol": "AMD",
                        "contractSymbol": "AMD250516P00090000",
                        "type": "PUT",
                        "strikePrice": 90.0,
                        "expirationDate": "2025-05-16",
                        "premiumPerContract": 0.80,
                        "exitPremium": 1.20,
                        "score": 7.0,
                        "contractsToBuy": 6
                        }
                    ],
                    "totalPremiumUsed": 480.0
                    }

                    """   
                },
                {
                    "role": "user",
                    "content": f"""
                        Here is the payload:
                        {payload}

                        Please return only JSON conforming to this schema:
                                            OUTPUT SCHEMA:
                        {{
                        "selectedTrade(s)": [
                            {{
                            "symbol": string,
                            "contractSymbol": string,
                            "type": "CALL" | "PUT",
                            "strikePrice": float,
                            "expirationDate": string,
                            "premiumPerContract": float,
                            "exitPremium": float,
                            "score": float,
                            "contractsToBuy": integer
                            }},
                            ...
                        ],
                        "totalPremiumUsed": float
                        }}
                    """
                }
            ]
        )
        recommendation = responses.choices[0].message.content
        json_rec = json.loads(recommendation)
        return json_rec
    except Exception as e:
        logger.error(f"Error in macro_stock_options_analysis: {e}")
        return None

async def micro_stock_options_analysis(payload):
    try:
        responses = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0,
            top_p=1,
            messages=[
                {
                    "role": "system",
                    "content": """
                    You are a stock-options analysis agent. 
                    - Goal: Maximize portfolio profit via weekly options (2–14 day hold). 
                    - Always output a valid JSON matching the provided schema. 
                    - Use only the data in the payload; do not hallucinate.
                """
                },
                {
                    "role": "user",
                    "content": f"""
                    Here is the payload to analyze:
                    {payload}

                    Please return only JSON conforming to this schema:
                    {{
                    "type": "object",
                    "properties": {{
                        "symbol":    {{ "type": "string" }},
                        "bestTrade": {{
                        "type": "object",
                        "properties": {{
                            "contractSymbol":   {{ "type": "string" }},
                            "type":             {{ "type": "string", "enum": ["CALL","PUT"] }},
                            ...
                        }},
                        "required": ["contractSymbol","type","strikePrice","expirationDate","premiumPerContract","exitPremium"]
                        }},
                        "score": {{ "type": "number", "minimum": 0, "maximum": 10 }}
                    }},
                    "required": ["symbol","bestTrade","score"]
                    }}
                    ******
                    The *score is a number between 0 and 10, score the contract on how good the trade is likely to return a positive roi.
                    """
                }
            ],
        )    
        
        recommendation = responses.choices[0].message.content
        json_rec = json.loads(recommendation)
        return json_rec
        
    except Exception as e:
        logger.error(f"Error in micro_stock_options_analysis: {e}")
        return None

async def get_ai_stock_events(ticker):
    try:
        response = client.responses.create(
            model= MODEL_NAME,
            temperature=0,
            tools= [{ "type": "web_search_preview",
                      "search_context_size": "medium",
                      "user_location":{"type":"approximate","country":"US","city":"Austin","region":"Austin","timezone":"America/Chicago"},
                      }],
            input=[{
                "role":"system",
                "content": f"""You are Expert Options Trader, a financial assistant that provides stock market information on fundementals and corporate events for {ticker} in the following JSON Format:
                Output Format (EXAMPLE):
                    "fundamentals": {{
                        "earnings": {{
                            "nextEarningsDate": "2025-05-08",
                            "lastEarningsDate": "2025-02-01",
                            "estimatedEarnings": 1.45,
                            "actualEarnings": 1.60,
                            "earningsSurprisePercent": 10.3
                        }},
                        "dividends": {{
                            "nextDividendDate": "2025-05-15",
                            "dividendAmount": 0.24,
                            "dividendYield": 0.006
                        }},
                        "beta": 1.15,
                        "marketCap": 2800000000000,
                        "events": [
                            {{
                                "type": "product_launch",
                                "description": "Expected iPhone 17 launch",
                                "date": "2025-05-12"
                            }},
                            {{
                                "type": "analyst_day",
                                "description": "Investor presentation and updated guidance",
                                "date": "2025-05-20"
                            }},
                            {{
                                "type": "regulatory_decision",
                                "description": "DOJ antitrust review conclusion",
                                "date": "2025-05-06"
                            }}
                        ]
                    }}
                """
                },
                {"role":"user",
                 "content": f"""what are the fundamental and corporate events for {ticker} in the next 30 days?"""
                            }
                
                ]
        )
        # Extract and parse the JSON
        pattern = r'```json\s*(.*?)\s*```'
        match = re.search(pattern, response.output_text, re.DOTALL)
        if not match:
            return None
        
        json_str = match.group(1)
        parsed_data = json.loads(json_str)
        fundamentals = parsed_data.get("fundamentals", {})
        return fundamentals
    except Exception as e:
        logger.error(f"Error in get_ai_stock_events: {e}")
        return None
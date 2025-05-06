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
    pass

async def micro_stock_options_analysis(payload):
    try:
        responses = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0,
            top_p=1,
            messages=[
                {
                    "role": "system",
                    "content": """You are a Stock Options Agent looking to Maximize portfolio profits through weekly options, holding for at most 2 weeks and at least 2 days, you will be provided with the follwoing Payload:
                    Payload Format:
                                            {
                            "symbol": "AAPL",
                            "quote": { … },
                            "optionsChain": [ … ],
                            "historicalPrices": [ … ],
                            "fundamentals": { … }
                            }
                            
                    You will need to provide a JSON response with the following format:
                    {
                        "symbol": "AAPL", (*ticker)
                        "bestTrade": {
                            "contractSymbol": "AAPL250509C00200000", (*contractSymbol)
                            "type": "CALL", (*type)
                            "strikePrice": 200.0, (*strikePrice)
                            "expirationDate": "2025-05-09", (*expirationDate)
                            "premiumPerContract": 2.88 (*premiumPerContract)
                            "exitPremium": 3.50, (*exitPremium)
                        },
                        "score": 7.5 (*score)
                    }
                    ******
                    The *score is a number between 0 and 10, score the contract on how good the trade is likely to return a positive roi.
                    
                    """
                },
                {
                    "role": "user",
                    "content": f"Analyze the following payload and provide a recommendation: {payload}"
                }
            ],
        )    
        
        recommendation = responses.choices[0].message.content
        logger.info(f"Recommendation: {recommendation}")
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
                            }]
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
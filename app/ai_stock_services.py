# from cachetools import TTLCache
from openai import OpenAI
from dotenv import load_dotenv
import re
import json
import os
import logging

logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4.1"
client = OpenAI()
client.api_key = os.getenv("OPENAI_API_KEY")

with open("app/resources/prompts/micro_analysis_system.txt", encoding="utf-8") as f:
    micro_analysis_system_mesage = f.read()
with open("app/resources/prompts/stock_recommendations_system.txt", encoding="utf-8") as f:
    stock_recommendations_system_mesage = f.read()
with open("app/resources/prompts/stock_recommendations_user.txt", encoding="utf-8") as f:
    stock_recommendations_user_mesage = f.read()

class AiTools:
    async def get_ai_stock_recommendations(self):
        try:
            response = client.responses.create(
                model= MODEL_NAME,
                temperature=0,
                top_p=1,
                tools= [{ "type": "web_search_preview",
                        "search_context_size": "medium",
                        "user_location":{"type":"approximate","country":"US","city":"Austin","region":"Austin","timezone":"America/Chicago"},
                        }],
                input=[{
                        "role":"system",
                        "content": stock_recommendations_system_mesage
                    },
                    {
                        "role":"user",
                        "content": stock_recommendations_user_mesage
                    }
                    
                    ]
            )
            data = response.output_text
            json_data = json.loads(data)
            candidates = json_data.get("candidates", [])
            return candidates
        except Exception as e:
            logger.error(f"Error in get_ai_stock_events: {e}")
            return None

    async def micro_stock_options_analysis(self,payload):
        try:
            responses = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0,
                top_p=1,
                messages=[
                    {
                        "role": "system",
                        "content": micro_analysis_system_mesage
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
                            "required": ["contractSymbol","type","strikePrice","expirationDate","premiumPerContract"]
                            }},
                            "score": {{ "type": "number", "minimum": 0, "maximum": 10 }}
                        }},
                        "required": ["symbol","bestTrade","score"]
                        }}
                        """
                    }
                ],
            )    
            #                     The *score is a number between 0 and 10, score the contract on how good the trade is likely to return a positive roi.
            #                     Score (0–10) is computed as: 40% Probability of Profit (chance the option finishes ITM), 20% Expected ROI ((E[payoff]–premium)/premium), 10% Risk/Reward ratio ((POP/(1–POP))×ROI), 10% Theta‐decay drag (|Θ|×days-held/premium), 10% Liquidity score (inverse bid-ask spread × √(OI/OI_ref)), and 10% IV cheapness ((mean_IV–IV_today)/std_IV mapped to [0,1]).
            recommendation = responses.choices[0].message.content
            json_rec = json.loads(recommendation)
            #add the score from the payload to the json_rec
            return json_rec
            
        except Exception as e:
            logger.error(f"Error in micro_stock_options_analysis: {e}")
            return None

    async def get_ai_stock_events(self,ticker):
        try:
            response = client.responses.create(
                model= MODEL_NAME,
                temperature=0,
                top_p=1,
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
# from cachetools import TTLCache
from openai import OpenAI
from dotenv import load_dotenv
import re
import json
import os
import logging

logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4.1-2025-04-14"
CHEAP_MODEL_NAME = "gpt-4.1-mini-2025-04-14"
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
            response = client.responses.parse(
                model=CHEAP_MODEL_NAME,
                temperature=0,
                top_p=1,
                tools=[
                    {
                        "type": "web_search_preview",
                        "search_context_size": "medium",
                        "user_location": {
                            "type": "approximate",
                            "country": "US",
                            "city": "Austin",
                            "region": "Austin",
                            "timezone": "America/Chicago"
                        }
                    }
                ],
                input = [
                    {
                        "role": "system",
                        "content": stock_recommendations_system_mesage
                    },
                    {
                        "role": "user",
                        "content": stock_recommendations_user_mesage
                    }
                ],
            )
            if "json" in response.output_text:
                json_data = self._strip_json(response.output_text)
            else:
                data = response.output_text
                json_data = json.loads(data)
            candidates = json_data.get("candidates", [])
            return candidates
        except Exception as e:
            logger.error(f"Error in get_ai_stock_recommendation: {e}")
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
            recommendation = responses.choices[0].message.content
            json_rec = json.loads(recommendation)

            return json_rec
            
        except Exception as e:
            logger.error(f"Error in micro_stock_options_analysis: {e}")
            return None

    async def get_ai_stock_events(self,ticker):
        try:
            response = client.responses.parse(
                model=CHEAP_MODEL_NAME,
                temperature=0,
                top_p=1,
                tools=[
                    {
                        "type": "web_search_preview",
                        "search_context_size": "medium",
                        "user_location": {
                            "type": "approximate",
                            "country": "US",
                            "city": "Austin",
                            "region": "Austin",
                            "timezone": "America/Chicago"
                        }
                    }
                ],
                input=[{
                    "role":"system",
                    "content": f"""
                    You are Expert Options Trader, a financial assistant that provides stock market information on fundementals and corporate events for {ticker}. 
                    
                    YOU MUST RESPOND ONLY WITH VALID JSON. DO NOT INCLUDE ANY EXPLANATORY TEXT OUTSIDE THE JSON.
                    
                    Your response must strictly follow this JSON format:
                    {{
                        "fundamentals": {{
                            "earnings": {{
                                "nextEarningsDate": "YYYY-MM-DD",
                                "lastEarningsDate": "YYYY-MM-DD",
                                "estimatedEarnings": 0.00,
                                "actualEarnings": 0.00,
                                "earningsSurprisePercent": 0.0
                            }},
                            "dividends": {{
                                "nextDividendDate": "YYYY-MM-DD",
                                "dividendAmount": 0.00,
                                "dividendYield": 0.000
                            }},
                            "beta": 0.00,
                            "marketCap": 0,
                            "events": [
                                {{
                                    "type": "event_type",
                                    "description": "event description",
                                    "date": "YYYY-MM-DD"
                                }}
                            ]
                        }}
                    }}
                    """
                    },
                    {"role":"user",
                    "content": f"""what are the fundamental and corporate events for {ticker} in the next 30 days?"""
                                }
                    
                    ]
            )
            
            if "json" in response.output_text:
                json_data = self._strip_json(response.output_text)
            else:
                data = response.output_text
                json_data = json.loads(data)
            fundamentals = json_data.get("fundamentals", {})
            return fundamentals
        except Exception as e:
            logger.error(f"Error in get_ai_stock_events: {e}")
            return None
        
    def _strip_json(self, json_str):
        try:
            pattern = r'```json\s*(.*?)\s*```'
            match = re.search(pattern, json_str, re.DOTALL)
            if not match:
                return None
            
            json_str = match.group(1)
            parsed_data = json.loads(json_str)
            return parsed_data
        except Exception as e:
            logger.error(f"Error in _strip_json: {e}")
            return None
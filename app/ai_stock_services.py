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
                    "content": f"""
                    You are a Market Scanner Agent.  
                    Every day, you will:
                    1. fetch the latest list of top stocks (e.g., top gainers, most active, highest volume).
                    3. Return a JSON array `candidates` of tickers to feed into the options‐analysis pipeline. 

                    Output Format (EXAMPLE):
                        {{
                            "candidates:["AAPL","MSFT","GOOGL","AMZN","TSLA","NFLX",...]
                        }} 
                    """
                    },
                    {
                        "role":"user",
                        "content": f"""
                        Fetch today’s top 10 most‐active U.S. equities from a reliable finance news site (e.g. CNBC, Yahoo Finance).
                        Output the results in the JSON format specified above ONLY.
                        """
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
                        "content": """
                            You are a stock-options analysis agent specializing in selecting optimal trades.
                            
                            IMPORTANT: Each contract in the options chain already has a pre-calculated score between 0-10 
                            that factors in:
                            - 40%: Probability of Profit (via delta)
                            - 20%: Expected ROI
                            - 10%: Risk/Reward ratio
                            - 10%: Theta decay drag
                            - 10%: Liquidity score (bid-ask spread and open interest)
                            - 10%: IV cheapness (relative to expiration date average)
                            
                            YOUR TASK:
                            1. Review the options chain in the payload
                            2. Select the contract with the highest score as your primary recommendation
                            3. Consider market context from fundamentals and events when finalizing your recommendation
                            4. Return the highest-scoring contract that aligns with the current market environment
                            5. Maintain the provided score from the contract rather than creating your own
                            
                            - Hold period: Typically 2-14 day positions
                            - Always output a valid JSON matching the provided schema
                            - Do not hallucinate data not present in the payload
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
            return json_rec
            
        except Exception as e:
            logger.error(f"Error in micro_stock_options_analysis: {e}")
            return None

    async def get_ai_stock_events(self,ticker):
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
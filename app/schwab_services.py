from app.schwabdev.client import Client as SchwabClient
from dotenv import load_dotenv
from datetime import datetime,timedelta
import math
import logging
import os
import asyncio
import statistics
import json
import pulp
from calendar import month_abbr

logger = logging.getLogger(__name__)
load_dotenv()
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
APP_CALLBACK_URL = os.getenv("APP_CALLBACK_URL")
schwab_client = SchwabClient(APP_KEY, APP_SECRET, APP_CALLBACK_URL)
global available_cash
global account_id

class SchwabTools:
    def __init__(self):
        self.available_cash,self.account_hash = self.get_schwab_available_cash()
        
    def get_schwab_available_cash(self):
        account = ((schwab_client.account_details_all()).json())[0]
        account_hash = ((schwab_client.account_linked()).json())[0]['hashValue']
        
        account_id = account['securitiesAccount']['accountNumber']
        available_cash = account['securitiesAccount']['currentBalances']['availableFunds']
        
        return available_cash,account_hash

    def get_core_quote(self,ticker):
        response = schwab_client.quotes(ticker)#can send a list of tickers to get multiple quotes
        data = response.json()
        quote = (self._parse_quote(data, ticker))
        return quote

    def get_options_chain(self,tickers_strike_dict):
        options_chain_list = []
        for ticker, strike_price in tickers_strike_dict.items():
            
            #TODO: May have to add argument for expiration month, strike count
            current_date =  (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
            current_date_plus_14 = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            response = schwab_client.option_chains(symbol=ticker,contractType="ALL",strikeCount=9,
                                                strike=strike_price, includeUnderlyingQuote=False,fromDate=current_date,toDate=current_date_plus_14)
            contract_list = []
            data = response.json()
            
            #Extract calls
            call_exp_map = data.get("callExpDateMap", {})
            # contract_list = _extract_contract_info(call_exp_map, contract_list)
            # Extract puts
            put_exp_map = data.get("putExpDateMap", {})
            # contract_list = _extract_contract_info(put_exp_map, contract_list)
            combined_exp_map = {**call_exp_map, **put_exp_map}
            contract_list = self._extract_contract_info(combined_exp_map, contract_list)
            
            options_chain_list.append({'ticker':ticker, 'options':contract_list})
            contract_list = []  # Reset for the next ticker

        
        return options_chain_list

    def get_price_history(self, ticker, periodType="month"):
        response = schwab_client.price_history(ticker, periodType=periodType,period=1, frequencyType="daily")
        data = response.json()
        
        candles = data.get("candles")
        hist_pr_list=[]
        for candle in candles:
            date = datetime.fromtimestamp(candle['datetime'] / 1000).strftime('%Y-%m-%d')
            close_price = candle['close']
            hist_pr_list.append({'date': date, 'close': close_price})
        return hist_pr_list
        
    def place_order(self,list_of_trades, account_hash):
        try:
            
            for trade in list_of_trades:
                # Extract trade details
                contract_symbol = trade['contractSymbol']
                premium_per_contract = trade['premiumPerContract']
                exit_premium = trade['exitPremium']
                contracts_to_buy = trade['contractsToBuy']
                
                
                order = {
                    "orderType": "LIMIT",
                    "session": "NORMAL",
                    "price": premium_per_contract,
                    'duration': "GOOD_TILL_CANCEL",
                    "orderStrategyType": "SINGLE",
                    "complexOrderStrategyType": "NONE",
                    "orderLegCollection": [
                        {
                            "instruction": "BUY_TO_OPEN",
                
                            "quantity": contracts_to_buy,
                            "instrument": {
                                "symbol": contract_symbol,
                                "assetType": "OPTION",
                            }
                        }
                    ]
                }
                # Place order using Schwab API
                response = schwab_client.order_place(account_hash,order)

        except Exception as e:
            logger.error(f"Error in place_order: {e}")
            return None
        
    def optimal_trade_selection(self,payload):
        # Convert budget to cents
        budget_cents = int(round(payload['availableCash'] * 100))
        
        trades = payload['bestTradesList']
        # Prepare items: cost in cents, value (score), index
        items = []
        for idx, item in enumerate(trades):
            premium = item['bestTrade']['premiumPerContract']
            cost_cents = int(round(premium * 100 * 100))  # premiumPerContract * 100 contracts * 100 cents
            if cost_cents <= 0 or cost_cents > budget_cents:
                continue
            items.append((idx, cost_cents, item['score']))
        
        # DP arrays
        dp = [0.0] * (budget_cents + 1)
        choice = [-1] * (budget_cents + 1)
        
        # Unbounded knapsack
        for b in range(budget_cents + 1):
            for idx, cost, value in items:
                if cost <= b:
                    new_val = dp[b - cost] + value
                    if new_val > dp[b]:
                        dp[b] = new_val
                        choice[b] = idx
        
        # Backtrack to find quantities
        remaining = budget_cents
        counts = {idx: 0 for idx, _, _ in items}
        while remaining > 0 and choice[remaining] != -1:
            idx = choice[remaining]
            cost = next(c for i, c, v in items if i == idx)
            counts[idx] += 1
            remaining -= cost
        
        # Build result
        selected = []
        total_used_cents = 0
        for idx, count in counts.items():
            if count > 0:
                item = trades[idx]
                trade = item['bestTrade']
                cost_per_contract = trade['premiumPerContract'] * 100
                used = int(round(cost_per_contract * count * 100)) / 100.0
                total_used_cents += int(round(cost_per_contract * count * 100))
                selected.append({
                    'symbol': item['symbol'],
                    'contractSymbol': trade['contractSymbol'],
                    'type': trade['type'],
                    'strikePrice': trade['strikePrice'],
                    'expirationDate': trade['expirationDate'],
                    'premiumPerContract': trade['premiumPerContract'],
                    'exitPremium': trade['exitPremium'],
                    'score': item['score'],
                    'contractsToBuy': count
                })
        
        total_used = total_used_cents / 100.0
        return {
            'selectedTrades': selected,
            'totalPremiumUsed': total_used
        }

    def diversified_trade_selection(self, payload, max_symbol_pct=0.5):
        # Budget
        budget = payload['availableCash']
        
        trades = payload['bestTradesList']
        
        # Define problem
        prob = pulp.LpProblem("Diversified_Trade_Selection", pulp.LpMaximize)
        
        # Decision variables: number of contracts per trade (integer)
        x = {
            i: pulp.LpVariable(f"x_{i}", lowBound=0, cat="Integer")
            for i in range(len(trades))
        }
        
        # Objective: maximize total score
        prob += pulp.lpSum([trades[i]['score'] * x[i] for i in x])
        
        # Budget constraint
        prob += pulp.lpSum([trades[i]['bestTrade']['premiumPerContract'] * 100 * x[i] for i in x]) <= budget
        
        # Diversification constraint: no single symbol consumes more than max_symbol_pct of budget
        for symbol in set(t['symbol'] for t in trades):
            prob += pulp.lpSum([
                trades[i]['bestTrade']['premiumPerContract'] * 100 * x[i]
                for i in x if trades[i]['symbol'] == symbol
            ]) <= max_symbol_pct * budget
        
        # Solve
        prob.solve()
        
        # Build result
        selected = []
        total_used = 0.0
        for i in x:
            count = int(pulp.value(x[i]))
            if count > 0:
                trade = trades[i]['bestTrade']
                cost = trade['premiumPerContract'] * 100 * count
                total_used += cost
                selected.append({
                    'symbol': trades[i]['symbol'],
                    'contractSymbol': trade['contractSymbol'],
                    'type': trade['type'],
                    'strikePrice': trade['strikePrice'],
                    'expirationDate': trade['expirationDate'],
                    'premiumPerContract': trade['premiumPerContract'],
                    'exitPremium': round((trade['premiumPerContract'])*1.3, 2),
                    'score': trades[i]['score'],
                    'contractsToBuy': count
                })
        
        return {
            'selectedTrades': selected,
            'totalPremiumUsed': total_used
        }
        
    def _extract_contract_info(self,exp_map, contract_list):
            # Collect contracts by expiration date
        expiration_contracts_map = {}

        for exp_date, strikes in exp_map.items():
            for strike_price, contracts in strikes.items():
                for contract in contracts:
                    symbol = contract.get("symbol")
                    expiration = contract.get("expirationDate")
                    ctype = contract.get("putCall")
                    strike = contract.get("strikePrice")
                    bid = contract.get("bid")
                    ask = contract.get("ask")
                    last = contract.get("last")
                    open_interest = contract.get("openInterest")
                    volume = contract.get("totalVolume")
                    implied_volatility = contract.get("volatility")
                    delta = contract.get("delta")
                    gamma = contract.get("gamma")
                    theta = contract.get("theta")
                    vega = contract.get("vega")

                    contract_obj = {
                        "expiration_date": expiration,
                        "contract_symbol": symbol,
                        "strike_price": strike,
                        "type": ctype,
                        "bid": bid,
                        "ask": ask,
                        "last": last,
                        "open_interest": open_interest,
                        "volume": volume,
                        "implied_volatility": implied_volatility,
                        "delta": delta,
                        "gamma": gamma,
                        "theta": theta,
                        "vega": vega
                    }
                    contract_list.append(contract_obj)
                    
                    # Group contracts by their expiration (exp_date key, as returned by Schwab)
                    expiration_contracts_map.setdefault(exp_date, []).append(contract_obj)

        # Compute IV stats for each expiration date, then attach results to each contract in that group
        for exp_date, contracts_for_exp in expiration_contracts_map.items():
            iv_values = [c["implied_volatility"] for c in contracts_for_exp if c["implied_volatility"] is not None]
            if iv_values:
                stats = {
                    "expiration_date": exp_date,
                    "min": min(iv_values),
                    "max": max(iv_values),
                    "mean": statistics.mean(iv_values),
                    "std": statistics.pstdev(iv_values)  # population stdev = pstdev
                }
                for c in contracts_for_exp:
                    c["iv_stats"] = stats  # attach stats to each contract
        self._score_contracts(contract_list)
        return contract_list

    def _score_contracts(self,contract_list):
        
        logger = logging.getLogger(__name__)
        
        # At the beginning of _score_contracts
        all_open_interests = [c.get("open_interest", 0) for c in contract_list if c.get("open_interest", 0) > 0]
        if all_open_interests:
            OI_REF = max(1000, statistics.median(all_open_interests) * 2)  # Median × 2 as reference
        else:
            OI_REF = 5000  # Fallback value
        
        for contract in contract_list:
            try:
                # Extract contract data
                option_type = contract["type"]
                strike = contract["strike_price"]
                delta = contract.get("delta", 0)
                implied_vol = contract.get("implied_volatility", 0) / 100  # Convert from percentage
                theta = abs(contract.get("theta", 0))
                bid = contract.get("bid", 0)
                ask = contract.get("ask", 0)
                open_interest = contract.get("open_interest", 0)
                
                # IV stats
                iv_stats = contract.get("iv_stats", {})
                iv_mean = iv_stats.get("mean", implied_vol * 100) / 100
                iv_std = iv_stats.get("std", 1) / 100
                iv_current = implied_vol
                
                # Calculate premium (mid-price)
                premium = (bid + ask) / 2 if bid and ask else 0
                
                # Calculate days to expiration
                exp_date = datetime.strptime(contract["expiration_date"].split('T')[0], "%Y-%m-%d")
                current_date = datetime.now()
                days_to_expiration = max(1, (exp_date - current_date).days + 1)
                
                score_components = {}
                
                # 1. Calculate Probability of Profit (40%)
                if option_type == "PUT":
                    pop = 1 - abs(delta) if delta else 0.5  # POP for puts
                else:  # CALL
                    pop = delta if delta else 0.5  # POP for calls
                
                pop_score = pop * 10  # Scale to 0-10
                score_components["pop_score"] = pop_score * 0.4
                
                # 2. Expected ROI (20%)
                if premium > 0:
                    # Simplified expected ROI calculation
                    if option_type == "PUT":
                        exp_roi = (pop * premium - (1-pop) * (strike - premium)) / premium
                    else:  # CALL
                        exp_roi = (pop * (strike - premium) - (1-pop) * premium) / premium
                        
                    exp_roi = min(1.0, max(-1.0, exp_roi))  # Clamp to [-1, 1]
                else:
                    exp_roi = 0
                    
                exp_roi_score = (exp_roi + 1) * 5  # Scale from [-1,1] to [0,10]
                score_components["exp_roi_score"] = exp_roi_score * 0.2
                
                # 3. Risk/Reward ratio (10%)
                if 0 < pop < 0.99:  # Avoid division by zero
                    risk_reward = (pop / (1 - pop)) * max(0, exp_roi)
                    # Normalize to 0-10 (using a log scale since risk/reward can get large)
                    risk_reward_score = min(10, max(0, math.log(1 + risk_reward) * 3))
                else:
                    risk_reward_score = 10 if pop >= 0.99 else 0
                    
                score_components["risk_reward_score"] = risk_reward_score * 0.1
                
                # 4. Theta decay drag (10%) - inverted so lower is better
                if premium > 0:
                    theta_drag = (theta * days_to_expiration) / premium
                    # Invert so lower values are better (less decay per premium dollar)
                    theta_drag_score = 10 / (1 + theta_drag * 2)  # Using a sigmoid-like function
                else:
                    theta_drag_score = 0
                
                score_components["theta_drag_score"] = min(10, max(0, theta_drag_score)) * 0.1
                
                # 5. Liquidity score (10%)
                if ask > bid > 0:
                    # Calculate inverse bid-ask spread
                    spread_pct = (ask - bid) / bid
                    inverse_spread = 1 / max(0.01, spread_pct)
                    
                    # Open interest factor (sqrt scale)
                    oi_factor = math.sqrt(max(1, open_interest) / OI_REF)
                    
                    liquidity_score = min(10, inverse_spread * oi_factor)
                else:
                    liquidity_score = 1  # Poor liquidity if invalid bid/ask
                    
                score_components["liquidity_score"] = liquidity_score * 0.1
                
                # 6. IV cheapness (10%)
                if iv_std > 0:
                    iv_z_score = (iv_mean - iv_current) / iv_std
                    # Convert z-score to a 0-10 scale where lower IV is better
                    iv_cheapness_score = min(10, max(0, (iv_z_score + 3) * 5/6))
                else:
                    iv_cheapness_score = 5  # Neutral score if std is 0
                    
                score_components["iv_cheapness_score"] = iv_cheapness_score * 0.1
                
                # Calculate final weighted score
                final_score = sum(score_components.values())
                final_scory = round(final_score, 2)
                # Store score and components in the contract object
                contract["score"] = final_scory
                
            except Exception as e:
                logger.error(f"Error scoring contract {contract.get('contract_symbol', 'unknown')}: {e}")
                contract["score"] = 0
                contract["score_components"] = {"error": str(e)}
        
        return contract_list

    def _parse_quote(self, json_response, ticker):
        try:
            last_price = json_response[ticker]['quote']['lastPrice']
            bid = json_response[ticker]['quote']['bidPrice']
            ask = json_response[ticker]['quote']['askPrice']
            open_price = json_response[ticker]['quote']['openPrice']
            high = json_response[ticker]['quote']['highPrice']
            low = json_response[ticker]['quote']['lowPrice']
            prev_close = json_response[ticker]['quote']['closePrice']
            volume = json_response[ticker]['quote']['totalVolume']
            average_volume_10_day = json_response[ticker]['fundamental']['avg10DaysVolume']
            timestamp = datetime.fromtimestamp((json_response[ticker]['quote']['quoteTime']) / 1000).isoformat()
            
            return {
                "symbol":ticker,
                "last_price":last_price,
                "bid":bid,
                "ask":ask,
                "open_price":open_price,
                "high":high,
                "low":low,
                "prev_close":prev_close,
                "volume":volume,
                "average_volume_10_day":average_volume_10_day,
                "timestamp":timestamp
            }
        except KeyError as e:
            logger.error(f"Key error: {e}")
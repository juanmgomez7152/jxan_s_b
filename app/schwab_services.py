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
        self.account_hash = None
        self.available_cash = self.get_schwab_available_cash()
        
    def get_schwab_available_cash(self):
        account = ((schwab_client.account_details_all()).json())[0]
        self.account_hash = ((schwab_client.account_linked()).json())[0]['hashValue']
        
        account_id = account['securitiesAccount']['accountNumber']
        available_cash = account['securitiesAccount']['currentBalances']['availableFunds']
        
        return available_cash

    def get_core_quote(self,ticker):
        response = schwab_client.quotes(ticker)
        data = response.json()
        quote = (self._parse_quote(data, ticker))
        return quote

    def get_options_chain(self,tickers_strike_dict):
        options_chain_list = []
        for ticker, strike_price in tickers_strike_dict.items():
            
            current_date =  (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
            current_date_plus_14 = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
            response = schwab_client.option_chains(symbol=ticker,contractType="ALL",strikeCount=9,
                                                strike=strike_price, includeUnderlyingQuote=False,fromDate=current_date,toDate=current_date_plus_14)
            contract_list = []
            data = response.json()
            
            call_exp_map = data.get("callExpDateMap", {})
            put_exp_map = data.get("putExpDateMap", {})

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
        
    async def place_order(self,trade):
        try:
            # Extract trade details
            contract_symbol = trade['contractSymbol']
            premium_per_contract = trade['premiumPerContract']
            stop_loss = trade['stop_loss']
            stop_price = trade['stop_price']
            exit_premium = trade['exitPremium']
            contracts_to_buy = trade['contractsToBuy']
            
            
            order = {
                "orderType": "LIMIT",
                "session": "NORMAL",
                "price": premium_per_contract,
                'duration': "DAY",
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
            #******************
            # Place order using Schwab API
            response = schwab_client.order_place(self.account_hash,order)
            if response.status_code != 201:
                raise Exception(f"Error placing order: {response.text}")
            #******************
            return {
                "premium_per_contract": premium_per_contract,
                "ticker": trade['symbol'],
                "type": trade['type'],
                "contract_symbol": contract_symbol,
                "premium": premium_per_contract,
                "exitPremium": exit_premium,
                "quantity": contracts_to_buy,
                "stop_loss": stop_loss,
                "stop_price": stop_price,
            }

        except Exception as e:
            logger.error(f"Error in place_order: {e}")
            return None
    
    async def _place_exit_oco_order(self,trade):
        stop_loss = trade['stop_loss']
        stop_price = trade['stop_price']
        exit_premium = trade['exitPremium']
        quantatity = trade['quantity']
        contract_symbol = trade['contract_symbol']
        try:
            oco_order = { 
                    "orderStrategyType": "OCO", 
                    "childOrderStrategies": [ 
                    { 
                        "orderType": "LIMIT", 
                        "session": "NORMAL", 
                        "price": exit_premium, 
                        "duration": "GOOD_TILL_CANCEL", 
                        "orderStrategyType": "SINGLE", 
                        "orderLegCollection": [ 
                            { 
                                "instruction": "SELL_TO_CLOSE", 
                                "quantity": quantatity, 
                                "instrument": { 
                                    "symbol": contract_symbol, 
                                    "assetType": "OPTION"
                                } 
                            } 
                        ] 
                    }, 
                    { 
                        "orderType": "STOP_LIMIT", 
                        "session": "NORMAL", 
                        "price": stop_loss, 
                        "stopPrice": stop_price, 
                        "duration": "GOOD_TILL_CANCEL", 
                        "orderStrategyType": "SINGLE", 
                        "orderLegCollection": [ 
                            { 
                                "instruction": "SELL_TO_CLOSE", 
                                "quantity": quantatity, 
                                "instrument": { 
                                    "symbol": contract_symbol, 
                                    "assetType": "OPTION" 
                                } 
                            } 
                        ] 
                    } 
                    ] 
                    }
            oco_response = schwab_client.order_place(self.account_hash,oco_order)
            if oco_response.status_code != 201:
                raise Exception(f"Error placing stop loss order: {oco_response.text}")
                
        except Exception as e:
            logger.error(f"Error in placing exit orders: {e}")
            return None    
    
    async def monitor_orders(self,payload):
        current_datetime = datetime.now()
        contract_symbol = payload['contract_symbol']
        ticker = payload['ticker']
        try:
            while True:
                filtered_filled_buy_data, filtered_filled_sell_data, filtered_working_data = self._get_status_lists(current_datetime)
                
                filled_b_order_found = any(payload['contract_symbol'] == order['orderLegCollection'][0]['instrument']['symbol'] for order in filtered_filled_buy_data)
                if not filled_b_order_found:#if the buy_to_open order is not filled check again immediately
                    continue
                
                filled_s_order_found = any(payload['contract_symbol'] == order['orderLegCollection'][0]['instrument']['symbol'] for order in filtered_filled_sell_data)
                if filled_s_order_found: #if the exit order is filled, break the loop
                    break
                
                working_order_found = any(contract_symbol == order['orderLegCollection'][0]['instrument']['symbol'] for order in filtered_working_data)
                if not working_order_found: #if the order is filled, theres no exit order filled, and the order to close has not been placed
                   await self._place_exit_oco_order(payload)
                   logger.info(f"Exit OCO order placed for {ticker}")
                   break
            return {"success": True,
                    "contract_symbol": contract_symbol,
                    "ticker": ticker,
                    "type": payload['type'],
                    "premium": payload['premium'],
                    "quantity": payload['quantity'],
                    "exit_premium": payload['exitPremium'],
                    "stop_loss": payload['stop_loss'],
                    "total_cost": round(payload['premium'] * payload['quantity'],2)*100,
                    "total_profit": round(payload['exitPremium'] * payload['quantity'] - payload['premium'] * payload['quantity'],2)*100,
                    "total_loss": round(payload['premium'] * payload['quantity'] - payload['stop_loss'] * payload['quantity'],2)*100,}
        except Exception as e:
            logger.error(f"Error in monitor_orders: {e}")
            return {"success": False,
                    "contract_symbol": contract_symbol}
            
    def _get_status_lists(self, date):
        try:
            response = schwab_client.account_orders(self.account_hash, date,date)#get all orders for the day
            all_orders = response.json()
            filled_buy_orders = [order for order in all_orders if order['orderLegCollection'][0]['instruction'] == "BUY_TO_OPEN" and order['status'] == "FILLED"]
            filled_sell_orders = [order for order in all_orders if order['orderLegCollection'][0]['instruction'] == "SELL_TO_CLOSE" and order['status'] == "FILLED"]
            working_orders = [order for order in all_orders if order['orderLegCollection'][0]['instruction'] == "SELL_TO_CLOSE" and order['status'] == "WORKING"]
            
            return filled_buy_orders, filled_sell_orders, working_orders
        except Exception as e:
            logger.error(f"Error in _get_status_lists: {e}")
            return [], [], []
    
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

    def diversified_trade_selection(self, payload, market_condition="NORMAL"):
        try:
            best_trades = payload["bestTradesList"]
            available_cash = payload['availableCash']
            
            # Create PuLP problem
            prob = pulp.LpProblem("Options_Selection", pulp.LpMaximize)
            
            # Integer variables for contract quantities (not just binary selection)
            # Each variable represents how many contracts to buy for each trade
            qty_vars = {f"qty_{i}": pulp.LpVariable(f"qty_{i}", lowBound=0, upBound=10, cat='Integer') 
                        for i in range(len(best_trades))}
            
            # Objective: Maximize total score × quantity (weighted by premium to favor cheaper contracts)
            prob += pulp.lpSum([
                best_trades[i]['score'] * qty_vars[f"qty_{i}"] * 
                (1 / max(0.12, best_trades[i]['bestTrade']['premiumPerContract']))  # Weight by inverse of premium
                for i in range(len(best_trades))
            ])
            
            # Constraint: Total cost must be within available cash (90%)
            prob += pulp.lpSum([
                best_trades[i]['bestTrade']['premiumPerContract'] * qty_vars[f"qty_{i}"]
                for i in range(len(best_trades))
            ]) <= available_cash * 0.9
            
            # Constraint: Diversification - no more than 50% per symbol
            symbols = set([trade['symbol'] for trade in best_trades])
            for symbol in symbols:
                symbol_indices = [i for i in range(len(best_trades)) 
                                if best_trades[i]['symbol'] == symbol]
                
                prob += pulp.lpSum([
                    best_trades[i]['bestTrade']['premiumPerContract'] * qty_vars[f"qty_{i}"]
                    for i in symbol_indices
                ]) <= available_cash * 0.5
            
            # Maximum number of distinct trades to select (avoid too many small positions)
            max_distinct_trades = min(5, len(best_trades))
            binary_selected = {f"selected_{i}": pulp.LpVariable(f"selected_{i}", cat='Binary') 
                            for i in range(len(best_trades))}
            
            # Link qty variables to binary selection variables
            for i in range(len(best_trades)):
                # If quantity > 0, then binary_selected = 1
                prob += qty_vars[f"qty_{i}"] <= 10 * binary_selected[f"selected_{i}"]
                # If binary_selected = 0, then quantity = 0
                prob += qty_vars[f"qty_{i}"] >= binary_selected[f"selected_{i}"]
            
            # Limit on number of distinct trades
            prob += pulp.lpSum([binary_selected[f"selected_{i}"] for i in range(len(best_trades))]) <= max_distinct_trades
            
            # Solve
            prob.solve(pulp.PULP_CBC_CMD(msg=0))
            
            # Get selected trades and their quantities
            selected = []
            total_premium_used = 0
            
            for i in range(len(best_trades)):
                contracts_to_buy = int(qty_vars[f"qty_{i}"].value())
                if contracts_to_buy > 0:
                    trade = best_trades[i]['bestTrade']
                    symbol = best_trades[i]['symbol']
                    premium = trade['premiumPerContract']
                    
                    # Get implied volatility value
                    iv = trade.get('impliedVolatility', 60)  # Default to 60% if not present
                    
                    # Adjust exit parameters based on market condition and IV
                    base_profit_factor = 1.0 + (iv/100)  # Base profit target
                    base_stop_factor = max(0.4, 0.65 - (iv/200))  # Base stop loss
                    
                    # Further adjust based on market condition
                    if market_condition == "HIGHLY_VOLATILE":
                        profit_factor = base_profit_factor * 1.2  # Higher profit targets in volatile markets
                        stop_factor = base_stop_factor * 0.9     # Tighter stops in volatile markets
                    elif market_condition == "VOLATILE":
                        profit_factor = base_profit_factor * 1.1
                        stop_factor = base_stop_factor * 0.95
                    elif market_condition == "LOW_VOLATILITY":
                        profit_factor = base_profit_factor * 0.9  # Lower targets in calm markets
                        stop_factor = base_stop_factor * 1.1      # Wider stops in calm markets
                    else:  # NORMAL
                        profit_factor = base_profit_factor
                        stop_factor = base_stop_factor
                    
                    # Calculate final exit parameters
                    exit_premium = round(premium * profit_factor, 2)
                    stop_loss = round(premium * stop_factor, 2)
                    stop_price = round(premium * (stop_factor + 0.05), 2)
                    
                    # Calculate total cost for this position
                    position_cost = round(premium * contracts_to_buy, 2)
                    total_premium_used += position_cost
                    
                    selected.append({
                        **trade,
                        'symbol': symbol,
                        'contractsToBuy': contracts_to_buy,
                        'exitPremium': exit_premium,
                        'stop_loss': stop_loss,
                        'stop_price': stop_price,
                        'total_cost': position_cost,
                        'total_profit': round((exit_premium - premium) * contracts_to_buy, 2),
                        'total_loss': round((premium - stop_loss) * contracts_to_buy, 2),
                    })
            
            return {"selectedTrades": selected, "totalPremiumUsed": total_premium_used}
        
        except Exception as e:
            logger.error(f"Error in diversified_trade_selection: {e}")
            return {"selectedTrades": []}
        
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
                
                # 1. Calculate Probability of Profit (35%)
                if option_type == "PUT":
                    pop = 1 - abs(delta) if delta else 0.5  # POP for puts
                else:  # CALL
                    pop = delta if delta else 0.5  # POP for calls
                
                pop_score = pop * 10  # Scale to 0-10
                score_components["pop_score"] = pop_score * 0.35
                
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
                
                # 4. Theta decay drag (7%) - inverted so lower is better
                if premium > 0:
                    theta_drag = (theta * days_to_expiration) / premium
                    # Invert so lower values are better (less decay per premium dollar)
                    theta_drag_score = 10 / (1 + theta_drag * 2)  # Using a sigmoid-like function
                else:
                    theta_drag_score = 0
                
                score_components["theta_drag_score"] = min(10, max(0, theta_drag_score)) * 0.07
                
                # 5. Liquidity score (8%)
                if ask > bid > 0:
                    # Calculate inverse bid-ask spread
                    spread_pct = (ask - bid) / bid
                    inverse_spread = 1 / max(0.01, spread_pct)
                    
                    # Open interest factor (sqrt scale)
                    oi_factor = math.sqrt(max(1, open_interest) / OI_REF)
                    
                    liquidity_score = min(10, inverse_spread * oi_factor)
                else:
                    liquidity_score = 1  # Poor liquidity if invalid bid/ask
                    
                score_components["liquidity_score"] = liquidity_score * 0.08
                
                # 6. IV cheapness (8%)
                if iv_std > 0:
                    iv_z_score = (iv_mean - iv_current) / iv_std
                    # Convert z-score to a 0-10 scale where lower IV is better
                    iv_cheapness_score = min(10, max(0, (iv_z_score + 3) * 5/6))
                else:
                    iv_cheapness_score = 5  # Neutral score if std is 0
                    
                score_components["iv_cheapness_score"] = iv_cheapness_score * 0.08
                
                # 7. NEW: Days to expiration score (12% - new component)
                # Maximum score at 8 days, gradually decreasing in both directions
                ideal_dte = 8  # Target 8 days to expiration
                dte_diff = abs(days_to_expiration - ideal_dte)
                
                if days_to_expiration < 3:  # Too short - rapid time decay risk
                    dte_score = 0
                elif days_to_expiration > 21:  # Too long - capital inefficient
                    dte_score = max(0, 3 - (days_to_expiration - 21) / 10)  # Small score for 21-30 DTE, 0 after
                else:
                    # Triangle function peaked at ideal_dte
                    dte_score = max(0, 10 - dte_diff * 1.5)  # Linear decrease from peak
                
                # If implied vol is high (>60%), prefer shorter DTE
                if implied_vol > 0.6:
                    shorter_dte_bonus = max(0, (0.8 - days_to_expiration/30) * 5)  # Bonus for shorter DTE in high IV
                    dte_score = max(dte_score, shorter_dte_bonus)  # Take the better score
                    
                score_components["dte_score"] = dte_score * 0.12  # New weight                
                
                # Calculate final weighted score
                final_score = sum(score_components.values())
                final_score_rounded = round(final_score, 2)
                # Store score and components in the contract object
                contract["score"] = final_score_rounded
                logger.debug(f"Contract {contract['contract_symbol']} DTE: {days_to_expiration}, Score: {final_score_rounded}")
 
                
            except Exception as e:
                logger.error(f"Error scoring contract {contract.get('contract_symbol', 'unknown')}: {e}")
                contract["score"] = 0
                contract["score_components"] = {"error": str(e)}
        
        return contract_list

    def _parse_quote(self, json_response, ticker):
        if ticker == "$VIX":
            return json_response[ticker]['quote']['lastPrice']
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
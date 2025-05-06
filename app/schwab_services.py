from app.schwabdev.client import Client as SchwabClient
from app.models.core_quote_model import CoreQuoteModel
from app.models.historical_volatility_model import HistoicalPrice
from app.models.fundamentals_model import FundamentalsModel
from app.ai_stock_services import get_ai_stock_events, micro_stock_options_analysis, macro_stock_options_analysis
from app.models.option_and_chain_model import OptionContract, OptionChainSnapshot
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List
import logging
import os
import asyncio
import statistics
import json
import pulp

logger = logging.getLogger(__name__)
load_dotenv()
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
APP_CALLBACK_URL = os.getenv("APP_CALLBACK_URL")
schwab_client = SchwabClient(APP_KEY, APP_SECRET, APP_CALLBACK_URL)
global available_cash
global account_id


def controller_schwab():
    print("Welcome to the Schwab API Controller")
    
    terminar = True
    while terminar:
        choice = input("Please select an option:")
        match choice:
            case "1":
                get_schwab_available_cash()
            case "2":
                list_of_tickers = ["MSFT", "AAPL", "GOOGL"]
                get_core_quote(list_of_tickers)
            case "3":
                dict_of_tickers: Dict[str, float] = {}
                dict_of_tickers["MSFT"] = 440
                # dict_of_tickers["AAPL"] = 190
                # dict_of_tickers["GOOGL"] = 165
                # dict_of_tickers["AMZN"] = 185
                get_options_chain(dict_of_tickers)
            case "4":
                ticker = "AAPL"
                get_price_history(ticker)
            case "5":
                ticker = "AAPL"
                get_ticker_events_and_fundamentals(ticker)
            case "6":
                ticker = "AAPL"
                temp_micro_orchestrator(ticker)
            case "7":
                list_of_best_trades = ["AAPL", "MSFT", "GOOGL"]
                temp_macro_orchestrator(list_of_best_trades)
            case "8":
                super_orchestrator()
            case "9":
                list_of_trades = ["AAPL", "MSFT", "GOOGL"]
                cash, account_hash = get_schwab_available_cash()
                place_order(list_of_trades,account_hash)
            case "x":
                print("Exiting...")
                terminar = False
            case _:
                print("Invalid choice")

def get_schwab_available_cash():
    account = ((schwab_client.account_details_all()).json())[0]
    account_hash = ((schwab_client.account_linked()).json())[0]['hashValue']
    
    account_id = account['securitiesAccount']['accountNumber']
    available_cash = account['securitiesAccount']['currentBalances']['availableFunds']
    
    return available_cash,account_hash

def get_core_quote(ticker) -> CoreQuoteModel:
    response = schwab_client.quotes(ticker)#can send a list of tickers to get multiple quotes
    data = response.json()
    quote = (_parse_quote(data, ticker))
    return quote

def get_options_chain(tickers_strike_dict):
    options_chain_list = []
    for ticker, strike_price in tickers_strike_dict.items():
        
        #TODO: May have to add argument for expiration month, strike count
        response = schwab_client.option_chains(symbol=ticker,contractType="ALL",strikeCount=9,
                                            strike=strike_price, includeUnderlyingQuote=False,expMonth="MAY")
        contract_list = []
        data = response.json()
        
        #Extract calls
        call_exp_map = data.get("callExpDateMap", {})
        # contract_list = _extract_contract_info(call_exp_map, contract_list)
        # Extract puts
        put_exp_map = data.get("putExpDateMap", {})
        # contract_list = _extract_contract_info(put_exp_map, contract_list)
        combined_exp_map = {**call_exp_map, **put_exp_map}
        contract_list = _extract_contract_info(combined_exp_map, contract_list)
        
        options_chain_list.append({'ticker':ticker, 'options':contract_list})
        contract_list = []  # Reset for the next ticker

    
    return options_chain_list

def get_price_history(ticker, periodType="month"):
    response = schwab_client.price_history(ticker, periodType=periodType,period=1, frequencyType="daily")
    data = response.json()
    
    candles = data.get("candles")
    hist_pr_list=[]
    for candle in candles:
        date = datetime.fromtimestamp(candle['datetime'] / 1000).strftime('%Y-%m-%d')
        close_price = candle['close']
        hist_pr_list.append({'date': date, 'close': close_price})
    return hist_pr_list

def get_ticker_events_and_fundamentals(ticker):
    try:
        events = asyncio.run(get_ai_stock_events(ticker))
        return events
    except Exception as e:
        logger.error(f"Error in get_ticker_events: {e}")
        return None
    
def place_order(list_of_trades, account_hash):
    try:
        
        for trade in list_of_trades:
            logger.info(f"Placing order for trade: {trade}")
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
            print(f"Order:\n {order}\n")
            # Place order using Schwab API
            response = schwab_client.order_place(account_hash,order)

    except Exception as e:
        logger.error(f"Error in place_order: {e}")
        return None
    
def super_orchestrator(): 
    
    trade1 = temp_micro_orchestrator("AAPL")
    trade2 = temp_micro_orchestrator("MSFT")
    trade3 = temp_micro_orchestrator("GOOGL")
    trade4 = temp_micro_orchestrator("AMZN")   
    
    list_of_best_trades = [trade1, trade2, trade3, trade4]
    # Get available cash
    available_cash,account_hash = get_schwab_available_cash()
    available_cash = available_cash * 0.8 # Use 80% of available cash for trading
    optimal_trades, diverse_trades = temp_macro_orchestrator(list_of_best_trades, available_cash)
    
    print(f"Optimal trades:\n {optimal_trades}")
    print(f"Diverse trades:\n {diverse_trades}")
    
    trades_to_order = diverse_trades['selectedTrades']
    place_order(trades_to_order, account_hash)
    

def temp_macro_orchestrator(list_of_best_trades, available_cash=800):
    try:
        payload = {
            "bestTradesList": list_of_best_trades,
            "availableCash": available_cash,
        }
        print(f"Payload: {payload}")
        trades_to_make = optimal_trade_selection(payload)
        diverse_trades = diversified_trade_selection(payload)
        return trades_to_make, diverse_trades
    except Exception as e:
        logger.error(f"Error in orchestrator: {e}")
        return None

def temp_micro_orchestrator(ticker):
    try:
        fundamentals_and_events = get_ticker_events_and_fundamentals(ticker)
        # logger.info(f"Fundamentals and Events for {ticker}: {fundamentals_and_events}")
        # Get available cash
        available_cash = get_schwab_available_cash()
        # logger.info(f"Available Cash: {available_cash}")
        # Get core quote
        core_quote = get_core_quote(ticker)
        # logger.info(f"Core Quote for {ticker}: {core_quote}")
        # Get options chain
        options_chain = get_options_chain({ticker: 440})
        
        # Get price history
        price_history = get_price_history(ticker)
        
        payload = {
            "symbol":ticker,
            "quote": core_quote,
            "optionsChain": options_chain,
            "historicalPrices": price_history,
            "fundamentals": fundamentals_and_events
        }

        best_trade = asyncio.run(micro_stock_options_analysis(payload))
        
        return best_trade
    
    except Exception as e:
        logger.error(f"Error in orchestrator: {e}")
        return None
    
def optimal_trade_selection(payload):
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


def diversified_trade_selection(payload, max_symbol_pct=0.5):
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
                'exitPremium': trade['exitPremium'],
                'score': trades[i]['score'],
                'contractsToBuy': count
            })
    
    return {
        'selectedTrades': selected,
        'totalPremiumUsed': total_used
    }
    
def _extract_contract_info(exp_map, contract_list) -> List[OptionContract]:
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
    return contract_list

def _parse_quote(json_response, ticker) -> CoreQuoteModel:
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
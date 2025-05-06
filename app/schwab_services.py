from app.schwabdev.client import Client as SchwabClient
from app.models.core_quote_model import CoreQuoteModel
from app.models.historical_volatility_model import HistoicalPrice
from app.models.fundamentals_model import FundamentalsModel
from app.ai_stock_services import get_ai_stock_events, micro_stock_options_analysis
from app.models.option_and_chain_model import OptionContract, OptionChainSnapshot
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List
import logging
import os
import asyncio
import statistics

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
                temp_orchestrator(ticker)
            case "x":
                print("Exiting...")
                terminar = False
            case _:
                print("Invalid choice")

def get_schwab_available_cash() -> float:
    response_accounts = schwab_client.account_details_all()
    accounts = response_accounts.json()
    
    account_id = accounts[0]['securitiesAccount']['accountNumber']
    available_cash = accounts[0]['securitiesAccount']['currentBalances']['availableFunds']
    
    return available_cash

def get_core_quote(ticker) -> CoreQuoteModel:
    response = schwab_client.quotes(ticker)#can send a list of tickers to get multiple quotes
    data = response.json()
    quote = (_parse_quote(data, ticker))
    return quote

def get_options_chain(tickers_strike_dict):
    options_chain_list = []
    for ticker, strike_price in tickers_strike_dict.items():
        
        #TODO: May have to add argument for expiration month, strike count
        response = schwab_client.option_chains(symbol=ticker,contractType="ALL",strikeCount=6,
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

def temp_orchestrator(ticker):
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

        micro_analysis = asyncio.run(micro_stock_options_analysis(payload))
    except Exception as e:
        logger.error(f"Error in orchestrator: {e}")
        return None
    
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
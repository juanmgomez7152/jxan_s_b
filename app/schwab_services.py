from app.schwabdev.client import Client as SchwabClient
from app.models.core_quote_model import CoreQuoteModel
from app.models.option_and_chain_model import OptionContract, OptionChainSnapshot
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, List
import logging
import os

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
        choice = input("Enter 1 to get accounts, 2 to get available cash, 3 to get positions: ")
        match choice:
            case "1":
                get_schwab_available_cash()
            case "2":
                list_of_tickers = ["MSFT", "AAPL", "GOOGL"]
                get_core_quote(list_of_tickers)
            case "3":
                dict_of_tickers: Dict[str, List[float]] = {}
                dict_of_tickers["MSFT"] = [440]
                dict_of_tickers["AAPL"] = [190]
                dict_of_tickers["GOOGL"] = [165]
                dict_of_tickers["AMZN"] = [185]
                get_options_chain(dict_of_tickers)
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
    
    logger.info(f"Account ID: {account_id}")
    logger.info(f"CASH AVAILABLE:{available_cash}")
    return available_cash

def get_core_quote(tickers=[]) -> List[CoreQuoteModel]:
    response = schwab_client.quotes(tickers)#can send a list of tickers to get multiple quotes
    data = response.json()
    quote_list = []
    for ticker in tickers:
        quote_list.append(_parse_quote(data, ticker))
    logger.info(f"# of Quotes: {len(quote_list)}")
    return quote_list

def get_options_chain(tickers_strike_dict) -> List[OptionChainSnapshot]:
    options_chain_list = []
    for ticker, strike_prices in tickers_strike_dict.items():
        for str_pr in strike_prices:
            response = schwab_client.option_chains(symbol=ticker,contractType="ALL",strikeCount=2,
                                                strike=str_pr, includeUnderlyingQuote=False,expMonth="MAY")
            contract_list = []
            data = response.json()
            
            #Extract calls
            call_exp_map = data.get("callExpDateMap", {})
            contract_list = _extract_contract_info(call_exp_map, contract_list)
            # Extract puts
            put_exp_map = data.get("putExpDateMap", {})
            contract_list = _extract_contract_info(put_exp_map, contract_list)
            
            print(f"Number of contracts for {ticker}: {len(contract_list)}")
            options_chain_list.append(OptionChainSnapshot(ticker=ticker, options=contract_list))
            contract_list = []  # Reset for the next ticker

    
    return options_chain_list

def _extract_contract_info(exp_map, contract_list):
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
                contract_list.append(OptionContract(expiration_date=expiration,
                                                    contract_symbol=symbol,
                                                    strike_price=strike,
                                                    type=ctype,
                                                    bid=bid,
                                                    ask=ask,
                                                    last=last,
                                                    open_interest=open_interest,
                                                    volume=volume,
                                                    implied_volatility=implied_volatility,
                                                    delta=delta,
                                                    gamma=gamma,
                                                    theta=theta,
                                                    vega=vega))
                    
    return contract_list

def _parse_quote(json_response, ticker):
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
        timestamp = datetime.fromtimestamp((json_response[ticker]['quote']['quoteTime']) / 1000)
        
        return CoreQuoteModel(
            symbol=ticker,
            last_price=last_price,
            bid=bid,
            ask=ask,
            open_price=open_price,
            high=high,
            low=low,
            prev_close=prev_close,
            volume=volume,
            average_volume_10_day=average_volume_10_day,
            timestamp=timestamp
        )
    except KeyError as e:
        logger.error(f"Key error: {e}")
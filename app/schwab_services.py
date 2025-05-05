from app.schwabdev.client import Client as SchwabClient
from app.models.core_quote_model import CoreQuoteModel
from app.models.option_and_chain_model import OptionContract, OptionChainSnapshot
from dotenv import load_dotenv
from datetime import datetime
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
                tickers = ["AAPL"]
                get_options_chain(tickers)
            case "x":
                print("Exiting...")
                terminar = False
            case _:
                print("Invalid choice")

def get_schwab_accounts():
    return schwab_client.account_details_all()

def get_schwab_available_cash():
    response_accounts = schwab_client.account_details_all()
    accounts = response_accounts.json()
    
    account_id = accounts[0]['securitiesAccount']['accountNumber']
    available_cash = accounts[0]['securitiesAccount']['currentBalances']['availableFunds']
    
    logger.info(f"Account ID: {account_id}")
    logger.info(f"CASH AVAILABLE:{available_cash}")
    return available_cash

def get_core_quote(tickers=[]):
    response = schwab_client.quotes(tickers)#can send a list of tickers to get multiple quotes
    json_response = response.json()
    quote_list = []
    for ticker in tickers:
        quote_list.append(_parse_quote(json_response, ticker))
        
    return quote_list

def get_options_chain(tickers=[], strike_prices = []):#Change strike_prices to a Dict with the ticker as key and a list of strike prices as value
    options_chain_list = []
    for ticker in tickers:
        for str_pr in strike_prices:
            response = schwab_client.option_chains(ticker, str_pr)
            json_response = response.json()
            options_chain = OptionChainSnapshot(
                expiration_date=json_response['expirationDate'],
                options=[OptionContract(
                    contract_symbol=option['contractSymbol'],
                    strike_price=option['strikePrice'],
                    type=option['type'],
                    bid=option['bidPrice'],
                    ask=option['askPrice'],
                    last=option['lastPrice'],
                    open_interest=option['openInterest'],
                    volume=option['volume'],
                    implied_volatility=option['impliedVolatility'],
                    delta=option['delta'],
                    gamma=option['gamma'],
                    theta=option['theta'],
                    vega=option['vega']
                ) for option in json_response['options']]
            )
            options_chain_list.append(options_chain)

    
    return options_chain_list

def get_options(ticker):
    pass

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
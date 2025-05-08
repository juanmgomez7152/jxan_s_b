from app.ai_stock_services import get_ai_stock_recommendations,micro_stock_options_analysis
from app.schwab_services import get_ticker_events_and_fundamentals,get_schwab_available_cash,get_core_quote,get_price_history,get_options_chain,place_order,optimal_trade_selection,diversified_trade_selection
from typing import Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)


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
            case "10":
                candidates = asyncio.run(get_ai_stock_recommendations())
            case "x":
                print("Exiting...")
                terminar = False
            case _:
                print("Invalid choice")
                
def super_orchestrator(): 
    # candidates = asyncio.run(get_ai_stock_recommendations())
    candidates = ["AAPL", "MSFT", "GOOGL"]
    list_of_best_trades = []
    # ********************************************************************
    # This needs to be async and concurrent
    for candidate in candidates:
        best_trade = temp_micro_orchestrator(candidate)
        if best_trade is not None:
            list_of_best_trades.append(best_trade)
    # ********************************************************************
    
    # Get available cash
    available_cash,account_hash = get_schwab_available_cash()
    available_cash = available_cash * 0.8 # Use 80% of available cash for trading
    logger.info(f"# of trades originally: {len(list_of_best_trades)}")
    list_of_best_trades = [trade for trade in list_of_best_trades if trade.get('score', 0) >= 7.5]
    logger.info(f"# of trades after filtering: {len(list_of_best_trades)}")
    for trade in list_of_best_trades:
        logger.info(f"Trade: \n{trade}")
    if not list_of_best_trades:
        logger.info("No trades met the minimum score threshold of 8.0")
        logger.info("Sentiment analysis: No trades to execute.")
        return
    diverse_trades = temp_macro_orchestrator(list_of_best_trades, available_cash)
    
    trades_to_order = diverse_trades['selectedTrades']
    for trade in trades_to_order:
        logger.info(f"Trade to order: \n{trade}")
    # place_order(trades_to_order, account_hash)
    

def temp_macro_orchestrator(list_of_best_trades, available_cash=800):
    try:
        payload = {
            "bestTradesList": list_of_best_trades,
            "availableCash": available_cash,
        }
        # trades_to_make = optimal_trade_selection(payload)
        diverse_trades = diversified_trade_selection(payload)
        return diverse_trades
    except Exception as e:
        logger.error(f"Error in orchestrator: {e}")
        return None

def temp_micro_orchestrator(ticker):
    try:
        fundamentals_and_events = get_ticker_events_and_fundamentals(ticker)
        # logger.info(f"Fundamentals and Events for {ticker}: {fundamentals_and_events}")
        # Get core quote
        core_quote = get_core_quote(ticker)
        atm_strike_price = round(core_quote["last_price"])
        # logger.info(f"Core Quote for {ticker}: {core_quote}")
        # Get options chain
        options_chain = get_options_chain({ticker: atm_strike_price})
        
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
        logger.error(f"Error in micro orchestrator: {e}")
        return None
    
    
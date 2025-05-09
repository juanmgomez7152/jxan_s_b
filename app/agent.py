from app.ai_stock_services import AiTools
from app.schwab_services import SchwabTools
from typing import Dict, List
from datetime import datetime, timedelta
import asyncio
import logging
import holidays
import time

logger = logging.getLogger(__name__)
HOURS_TO_TRADE = [9, 10 ]
DAYS_OF_WEEK_NOT_TO_TRADE = ["Mon", "Fri", "Sat", "Sun"]
CALENDAR_DAY_NOT_TO_TRADE = [1,2,3,4,5,25,26,27,28,29,30,31] # 1st and last day of the month
US_HOLIDAYS = ["New Year's Day","Martin Luther King Jr. Day", "Washington's Birthday","Good Friday","Memorial Day","Juneteenth National Independence Day","Independence Day","Labor Day","Thanksgiving Day","Christmas Day"]
holidays_US = holidays.US()

class AIStockAgent:
    def __init__(self):
        self.ai_tools = AiTools()
        self.schwab_tools = SchwabTools()
        logger.info("AIStockAgent initialized...")
    
    def run_ai_agent(self):
        logger.info("Running AI agent...")
        
        # self.get_into_trade_window()
        
        self.available_cash,self.account_hash = self.schwab_tools.get_schwab_available_cash()
        
        stocks_to_trade = asyncio.run(self.ai_tools.get_ai_stock_recommendations())

        # Process all tickers concurrently
        async def process_all_tickers():
            tasks = [self.micro_analysis(ticker) for ticker in stocks_to_trade]
            return await asyncio.gather(*tasks)
        
        # Run the async function and filter out None results
        list_of_best_trades = [trade for trade in asyncio.run(process_all_tickers()) if trade is not None]

        reduced_available_cash = self.available_cash * 0.8

        trades = self.macro_analsysis(list_of_best_trades, reduced_available_cash)

        self.schwab_tools.place_order(trades, self.account_hash)

    
    def get_into_trade_window(self):
        current_time = datetime.now()
        
        self.rest(current_time=current_time,function=self._check_beg_end_of_month)
        self.rest(current_time=current_time,function=self._check_holiday)
        self.rest(current_time=current_time,function=self._check_day_of_week_to_trade)
        self.rest(current_time=current_time,function = self._check_hour_to_trade)
    
    def rest(self,current_time=None,function=None, sleep_seconds=None):
        if function is None:
            time.sleep(sleep_seconds)
        else:
            sleep_seconds = function(current_time)
            while sleep_seconds is not None:
                logger.info(f"Sleeping for {sleep_second/3600:.2f} hours until next trading window")
                time.sleep(sleep_second)
                current_time = datetime.now()
                sleep_second = function(current_time)    
    
    def _check_beg_end_of_month(self, current_time):
        # Check if today is the first or last day of the month
        if current_time.day in CALENDAR_DAY_NOT_TO_TRADE:
            logger.info(f"Not trading today ({current_time.strftime('%Y-%m-%d')})")
            # Calculate time until next business day at 9 AM
            next_run = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            next_run = next_run + timedelta(days=1)
            while next_run.day in CALENDAR_DAY_NOT_TO_TRADE:
                next_run = next_run + timedelta(days=1)
            sleep_seconds = (next_run - current_time).total_seconds()
            return sleep_seconds
        else:
            return None
    
    def _check_holiday(self, current_time):
        current_date = current_time.strftime('%Y-%m-%d')
        if holidays_US.get(current_date) in US_HOLIDAYS:
            logger.info(f"Today is a holiday: {holidays_US[current_date]}")
            # Calculate time until next business day at 9 AM
            next_run = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            next_run = next_run + timedelta(days=1)
            while next_run.strftime('%Y-%m-%d') in holidays_US:
                next_run = next_run + timedelta(days=1)
            sleep_seconds = (next_run - current_time).total_seconds()
            return sleep_seconds
        else:
            return None
    
    def _check_day_of_week_to_trade(self, current_time):
        day_name = current_time.strftime("%a")
        if day_name not in ["Tue", "Wed", "Thu"]:
            logger.info(f"Not trading today ({day_name})")
            # Calculate time until next Tuesday 9 AM
            now = current_time
            days_ahead = {
                'Mon': 1,
                'Fri': 4, 
                'Sat': 3,
                'Sun': 2
            }.get(day_name)
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            next_run = next_run + timedelta(days=days_ahead)
            sleep_seconds = (next_run - now).total_seconds()
            return sleep_seconds
        else:
            return None
    
    def _check_hour_to_trade(self, current_time):
        if current_time.hour>=9 and current_time.hour<10:
            return True
        else:
            # Calculate time until 9 AM tomorrow
            now = datetime.now()
            next_run = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run = next_run.replace(day=now.day + 1)
            sleep_seconds = (next_run - now).total_seconds()
            return sleep_seconds
        
    
    def macro_analsysis(self, list_of_best_trades, available_cash):
        try:
            payload = {
                "bestTradesList": list_of_best_trades,
                "availableCash": available_cash,
            }
            # trades_to_make = self.schwab_tools.optimal_trade_selection(payload)
            diverse_trades = self.schwab_tools.diversified_trade_selection(payload)
            return diverse_trades
        
        except Exception as e:
            logger.error(f"Error in macro orchestrator: {e}")
            return None
        
    async def micro_analysis(self, ticker):
        try:
            fundamentals_and_events = await self.ai_tools.get_ai_stock_events(ticker)

            core_quote = self.schwab_tools.get_core_quote(ticker)

            atm_strike_price = round(core_quote["last_price"])
            options_chain = self.schwab_tools.get_options_chain({ticker: atm_strike_price})
            
            price_history = self.schwab_tools.get_price_history(ticker)
            
            payload = {
                "symbol":ticker,
                "quote": core_quote,
                "optionsChain": options_chain,
                "historicalPrices": price_history,
                "fundamentals": fundamentals_and_events
            }
            
            best_trade = await self.ai_tools.micro_stock_options_analysis(payload)
            
            return best_trade
    
        except Exception as e:
            logger.error(f"Error in micro orchestrator: {e}")
            return None
    
    def _is_holiday(self, date):
        # Check if the date is a holiday
        if date in US_HOLIDAYS:
            return True
        
        # Check if the date is a weekend
        if date.weekday() >= 5:
            logger.info(f"Today is a weekend day")
            return True
            
def controller_schwab():
    print("Welcome to the Schwab API Controller")
    
    terminar = True
    while terminar:
        choice = input("Please select an option:")
        match choice:
            case "1":
                get_schwab_available_cash()
            case "2":
                quote = get_core_quote("MSFT")
                logger.info(f"Quote:\n {quote}")
            case "3":
                dict_of_tickers: Dict[str, float] = {}
                dict_of_tickers["MSFT"] = 440
                # dict_of_tickers["AAPL"] = 190
                # dict_of_tickers["GOOGL"] = 165
                # dict_of_tickers["AMZN"] = 185
                option_chain = get_options_chain(dict_of_tickers)
                logger.info(f"Option Chain:\n {option_chain}")
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
                logger.info(f"Candidates: {candidates}")
            case "x":
                print("Exiting...")
                terminar = False
            case _:
                print("Invalid choice")
                
def super_orchestrator(): 
    # candidates = asyncio.run(get_ai_stock_recommendations())
    candidates = ["AAPL"]
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
    list_of_best_trades.sort(key=lambda x: x.get('score', 0), reverse=True)
    # list_of_best_trades = [trade for trade in list_of_best_trades if trade.get('score', 0) >= 7.5]
    logger.info(f"# of trades after filtering: {len(list_of_best_trades)}")
    
    diverse_trades = temp_macro_orchestrator(list_of_best_trades, available_cash)
    
    trades_to_order = diverse_trades['selectedTrades']
    possible_profit = 0
    total_cost = 0
    for trade in trades_to_order:
        logger.info(f"Trade to order: \n{trade}")
        total_cost = total_cost + (trade['premiumPerContract']*100*trade['contractsToBuy'])
        possible_profit = possible_profit + (trade['exitPremium']*100*trade['contractsToBuy'] - trade['premiumPerContract']*100*trade['contractsToBuy'])
    possible_profit = round(possible_profit, 2)
    logger.info(f"Possible profit: {possible_profit}")
        
        
    # place_order(trades_to_order, account_hash)
    

def temp_macro_orchestrator(list_of_best_trades, available_cash):
    try:
        payload = {
            "bestTradesList": list_of_best_trades,
            "availableCash": available_cash,
        }
        # trades_to_make = optimal_trade_selection(payload)
        diverse_trades = diversified_trade_selection(payload)
        return diverse_trades
    except Exception as e:
        logger.error(f"Error in macro orchestrator: {e}")
        return None

def temp_micro_orchestrator(ticker):
    try:
        fundamentals_and_events = get_ticker_events_and_fundamentals(ticker)

        core_quote = get_core_quote(ticker)
        atm_strike_price = round(core_quote["last_price"])
        
        options_chain = get_options_chain({ticker: atm_strike_price})
        
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
    

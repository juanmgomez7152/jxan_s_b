from app.ai_stock_services import AiTools
from app.schwab_services import SchwabTools
from app.trading_scheduling_tools import TradingSchedulingTools
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)

class AIStockAgent:
    def __init__(self):
        self.ai_tools = AiTools()
        self.schwab_tools = SchwabTools()
        self.trading_scheduling_tools = TradingSchedulingTools()
        logger.info("AIStockAgent initialized...")
    
    def run_ai_agent(self):
        logger.info("Running AI agent...")
        current_time = datetime.now()
        self.trading_scheduling_tools.get_into_trade_window(current_time=current_time)
        
        self.available_cash,self.account_hash = self.schwab_tools.get_schwab_available_cash()
        if self.available_cash < 200:
            logger.info("Available cash is less than $200. Sleeping until next trading window...")
            self.trading_scheduling_tools.sleep_until_next_trading_window(current_time=current_time)
        
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
        
        logger.info("AI Agent run completed. Sleeping until next trading window...")
        self.trading_scheduling_tools.sleep_until_next_trading_window(current_time=current_time)
        
        self.run_ai_agent()
    
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
            logger.error(f"Error in macro analysis: {e}")
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
            logger.error(f"Error in micro analysis: {e}")
            return None
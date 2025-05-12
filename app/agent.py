from app.ai_stock_services import AiTools
from app.schwab_services import SchwabTools
from app.trading_scheduling_tools import TradingSchedulingTools
from app.email_handler import EmailHandler
from datetime import datetime
import asyncio
import logging
import json

logger = logging.getLogger(__name__)

class AIStockAgent:
    def __init__(self):
        self.ai_tools = AiTools()
        self.schwab_tools = SchwabTools()
        self.trading_scheduling_tools = TradingSchedulingTools()
        self.email_handler = EmailHandler()
        logger.info("AIStockAgent initialized...")
    
    def run_ai_agent(self):
        logger.info("Running AI agent...")
        current_time = datetime.now()
        self.trading_scheduling_tools.get_into_trade_window(current_time=current_time)
        
        self.available_cash = self.schwab_tools.get_schwab_available_cash()
        if self.available_cash < 200:
            logger.info("Available cash is less than $200. Sleeping until next trading window...")
            self.email_handler._send_email(
                subject="Stock Bot: Low Cash Alert",
                body="Your Stock Bot has less than $200 available cash. It will not execute trades until the next trading window. Please check that there are no hazards.",)
            self.trading_scheduling_tools.sleep_until_next_trading_window(current_time=current_time)
        else:
            logger.info(f"Available cash: {self.available_cash}")
        
        stocks_to_trade = asyncio.run(self.ai_tools.get_ai_stock_recommendations())
        
        # Run the async function and filter out None results
        list_of_best_trades = [trade for trade in asyncio.run(self._process_all_tickers(stocks_to_trade)) if trade is not None]

        reduced_available_cash = self.available_cash * 0.8
        selected_trades = (self.macro_analsysis(list_of_best_trades, reduced_available_cash))["selectedTrades"]

        # Similar to how you handle list_of_best_trades
        order_status = [trade for trade in asyncio.run(self._process_all_orders(selected_trades)) if trade is not None]
        
        logger.info("AI Agent run completed. Sleeping until next trading window...")
        self.trading_scheduling_tools.sleep_until_next_trading_window(current_time=current_time)
        
        self.email_handler.send_trade_notification(selected_trades)
    
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
    async def _process_all_orders(self,selected_trades):
            tasks = [self.schwab_tools.place_order(trade) for trade in selected_trades]
            return await asyncio.gather(*tasks)
    
    async def _process_all_tickers(self, stocks_to_trade):
        tasks = [self.micro_analysis(ticker) for ticker in stocks_to_trade]
        return await asyncio.gather(*tasks)
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
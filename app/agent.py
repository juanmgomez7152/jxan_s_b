from app.ai_stock_services import AiTools
from app.schwab_services import SchwabTools
from app.trading_scheduling_tools import TradingSchedulingTools
from app.email_handler import EmailHandler
from datetime import datetime
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class AIStockAgent:
    def __init__(self):
        self.ai_tools = AiTools()
        self.schwab_tools = SchwabTools()
        self.trading_scheduling_tools = TradingSchedulingTools()
        self.email_handler = EmailHandler()
        logger.info("AIStockAgent initialized...")
    
    def run_ai_agent(self):
        asyncio.run(self.schwab_tools.monitor_orders([]))
        # logger.info("Running AI agent...")
        
        # self.available_cash = self.schwab_tools.get_schwab_available_cash()
        # if self.available_cash < 200:
        #     logger.info("Available cash is less than $200. Sleeping until next trading window...")
        #     self.email_handler._send_email(
        #         subject="Stock Bot: Low Cash Alert",
        #         body="Your Stock Bot has less than $200 available cash. It will not execute trades until the next trading window. Please check that there are no hazards.",)
        # else:
        #     logger.info(f"Available cash: {self.available_cash}")
        
        # stocks_to_trade = asyncio.run(self.ai_tools.get_ai_stock_recommendations())
        
        # list_of_best_trades = [trade for trade in asyncio.run(self._process_all_tickers(stocks_to_trade)) if trade is not None and trade['bestTrade'] is not None and trade['bestTrade']['premiumPerContract'] is not None and trade['score'] is not None]
        # fraction_cash = round(self.available_cash*0.01,2)
        # list_of_best_trades = [trade for trade in list_of_best_trades if trade['bestTrade']['premiumPerContract'] <= fraction_cash and trade['score'] >= 4.00 and trade['bestTrade']['premiumPerContract'] != 0.01]
        # selected_trades = (self.macro_analsysis(list_of_best_trades, self.available_cash))['selectedTrades']
        
        # refined_order_placed = [trade for trade in asyncio.run(self._process_all_orders(selected_trades)) if trade is not None]
        
        # exit_order_status = [trade for trade in asyncio.run(self._process_all_exits(refined_order_placed)) if trade is not None]
            
        # self.email_handler.send_trade_notification(selected_trades)
        
        # logger.info("AI Agent run completed. Sleeping until next trading window...")
    
    def macro_analsysis(self, list_of_best_trades, available_cash):
        try:
            payload = {
                "bestTradesList": list_of_best_trades,
                "availableCash": available_cash,
            }
            # optimal_trades = self.schwab_tools.optimal_trade_selection(payload)
            diverse_trades = self.schwab_tools.diversified_trade_selection(payload)
            return diverse_trades
        
        except Exception as e:
            logger.error(f"Error in macro analysis: {e}")
            return None
        
    async def _process_all_orders(self,selected_trades):
            tasks = [self.schwab_tools.place_order(trade) for trade in selected_trades]
            return await asyncio.gather(*tasks)

    async def _process_all_exits(self, trades):
        tasks = [self.schwab_tools.monitor_orders(trade) for trade in trades]
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
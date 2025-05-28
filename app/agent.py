from app.ai_stock_services import AiTools
from app.schwab_services import SchwabTools
from app.trading_scheduling_tools import TradingSchedulingTools
from app.web_scrapping_services import YahooFinanceScraper
from app.email_handler import EmailHandler
import asyncio
import logging

logger = logging.getLogger(__name__)

class AIStockAgent:
    def __init__(self):
        self.ai_tools = AiTools()
        self.schwab_tools = SchwabTools()
        self.trading_scheduling_tools = TradingSchedulingTools()
        self.email_handler = EmailHandler()
        self.yahoo_finance_scraper = YahooFinanceScraper()
        logger.info("AIStockAgent initialized...")
    
    async def run_ai_agent(self):
        start_time = asyncio.get_event_loop().time()
        logger.info("Running AI agent...")
        
        logger.info("Fetching market conditions...")
        min_score, max_allocation, market_conditions = self._get_market_conditions()
        
        self.available_cash = self.schwab_tools.get_schwab_available_cash()
        adjusted_cash = round(self.available_cash * max_allocation,2)
        
        if self.available_cash < 200:
            logger.info("Available cash is less than $200. Sleeping until next trading window...")
            self.email_handler._send_email(
                subject="Stock Bot: Low Cash Alert",
                body="Your Stock Bot has less than $200 available cash. It will not execute trades until the next trading window. Please check that there are no hazards.",)
        else:
            logger.info(f"Available cash: {self.available_cash}")
            
        logger.info("Fetching stock recommendations...")
        stock_recommendations = self.yahoo_finance_scraper.get_most_active_stocks()
        
        logger.info("Performing micro analysis on stock recommendations...")
        best_trades = [trade for trade in await (self._process_all_tickers(stock_recommendations)) if trade is not None]
        
        logger.info("Selecting the best trades to perform...")
        fraction_cash = round(adjusted_cash*0.01,2)
        filtered_best_trades = [trade for trade in best_trades if trade['premiumPerContract'] <= fraction_cash and trade['score'] >= min_score and trade['premiumPerContract'] >= 0.12]
        selected_trades = (self.macro_analsysis(filtered_best_trades, fraction_cash,market_conditions))['selectedTrades']
        
        logger.info("Placing orders for selected trades...")
        exit_payload = [trade for trade in await (self._process_all_orders(selected_trades)) if trade is not None]
        
        logger.info("Placing orders for exit trades...")
        
        exit_order_status = [trade for trade in await (self._process_all_exits(exit_payload)) if trade is not None and trade['success']]  
        for trade in exit_order_status:
            trade['extraContext'] = self.schwab_tools.get_ticker_info(trade['ticker'])
            trade['ai_sentiment'] = await self.ai_tools.trade_insight(trade)       
        self.email_handler.send_trade_notification(exit_order_status)
        
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time
        logger.info(f"AI Agent run completed. Execution time: {execution_time:.2f} seconds")
    
    def macro_analsysis(self, best_trades, available_cash,market_conditions):
        try:
            payload = {
                "bestTradesList": best_trades,
                "availableCash": available_cash,
            }
            # optimal_trades = self.schwab_tools.optimal_trade_selection(payload)
            diverse_trades = self.schwab_tools.diversified_trade_selection(payload,market_conditions)
            return diverse_trades
        
        except Exception as e:
            logger.error(f"Error in macro analysis: {e}")
            return None
        
    async def _process_all_orders(self,selected_trades):
            tasks = [self.schwab_tools.place_order(trade) for trade in selected_trades]
            return await asyncio.gather(*tasks)

    async def _process_all_exits(self, exit_payload):
        tasks = [self.schwab_tools.monitor_orders(trade) for trade in exit_payload]
        return await asyncio.gather(*tasks)
    
    async def _process_all_tickers(self, stock_recommendations):
        tasks = [self._get_best_contract(ticker) for ticker in stock_recommendations]
        return await asyncio.gather(*tasks)
    
    async def _get_best_contract(self, ticker):
        try:
            core_quote = self.schwab_tools.get_core_quote(ticker)
            atm_strike_price = round(core_quote["last_price"])
            options_chain,highest_scored_contract = self.schwab_tools.get_options_chain({ticker: atm_strike_price})
            if highest_scored_contract is None:
                raise ValueError(f"No options chain found for {ticker} at strike price {atm_strike_price}")
            highest_scored_contract['premiumPerContract'] = highest_scored_contract['last']
            highest_scored_contract['symbol'] = ticker
            return  highest_scored_contract
        except ValueError as ve:
            logger.debug(f"ValueError in getting best contract for {ticker}: {ve}")
            return None
        except Exception as e:
            logger.error(f"Error in getting best contract: {e}")
            return None
    
    async def micro_analysis(self, ticker):
        try:
            #use finhub API to get fundamentals and events
            fundamentals_task = self.ai_tools.get_ai_stock_events(ticker)
            fundamentals_and_events = await self.ai_tools.get_ai_stock_events(ticker)

            core_quote = self.schwab_tools.get_core_quote(ticker)
            price_history = self.schwab_tools.get_price_history(ticker)
            
            fundamentals_and_events = await fundamentals_task

            atm_strike_price = round(core_quote["last_price"])
            options_chain,highest_scored_contract = self.schwab_tools.get_options_chain({ticker: atm_strike_price})
            if highest_scored_contract is None:
                raise ValueError(f"No options chain found for {ticker} at strike price {atm_strike_price}")
            payload = {
                "symbol":ticker,
                "quote": core_quote,
                "optionsChain": options_chain,
                "historicalPrices": price_history,
                # "fundamentals": fundamentals_and_events
            }
            
            # best_trade = await self.ai_tools.micro_stock_options_analysis(payload)
            highest_scored_contract['premiumPerContract'] = highest_scored_contract['last']
            return  highest_scored_contract
        except ValueError as ve:
            logger.debug(f"ValueError in micro analysis for {ticker}: {ve}")
            return None  # Skip this ticker if no options chain is found
        except Exception as e:
            logger.error(f"Error in micro analysis: {e}")
            return None
        
    def _get_market_conditions(self):
        try:
            vix_level = self.schwab_tools.get_core_quote("$VIX")
            
            # Set trading parameters based on market volatility
            if vix_level > 30:
                market_conditions = "HIGHLY VOLATILE"
                min_score = 6.0  # Much more selective
                max_allocation = 0.6  # Reduce overall exposure
                logger.info(f"Market is HIGHLY VOLATILE (VIX: {vix_level}). Using conservative parameters.")
            elif vix_level > 20:
                market_conditions = "VOLATILE"
                min_score = 5.0  # More selective
                max_allocation = 0.8  # Slightly reduced exposure
                logger.info(f"Market is VOLATILE (VIX: {vix_level}). Using cautious parameters.")
            elif vix_level < 12:
                market_conditions = "CALM"
                min_score = 3.5  # Less strict
                max_allocation = 1.0  # Full allocation
                logger.info(f"Market is CALM (VIX: {vix_level}). Using standard parameters.")
            else:
                market_conditions = "NORMAL"
                min_score = 4.0  # Default
                max_allocation = 0.9  # Slight safety margin
                logger.info(f"Market is NORMAL (VIX: {vix_level}). Using default parameters.")
            return min_score, max_allocation, market_conditions
        except Exception as e:
            # Fallback to default values if VIX fetch fails
            logger.warning(f"Failed to fetch VIX level: {e}. Using default market parameters.")
            market_conditions = None
            min_score = 4.0
            max_allocation = 0.9
            return min_score, max_allocation, market_conditions
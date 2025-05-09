from datetime import datetime, timedelta
import time
import logging
import pandas_market_calendars as mcal

logger = logging.getLogger(__name__)
CALENDAR_DAY_NOT_TO_TRADE = [1,2,3,4,5,25,26,27,28,29,30,31] # 1st and last days of the month

class TradingSchedulingTools:
    def __init__(self):
        pass

    def get_into_trade_window(self, current_time=None):
        # current_time = datetime.now()

        if self.rest(current_time=current_time,function=self._check_beg_end_of_month): # This function checks if today is the first or last day of the month,
            return
        elif self.rest(current_time=current_time,function=self._check_day_of_week_to_trade): # This function checks if today is a day of the week to trade
            return
        elif (not self._is_market_open(current_time)) or  self._early_market_close(current_time): # This function checks if the market is open today (on holidays (observed holidays) it would be closed) and # This function checks if the market has early closing hours today
            pass
        else: # This function checks if the current time is within the trading hours
            self.rest(current_time=current_time,function = self._check_hour_to_trade)
    
    def sleep_until_next_trading_window(self, current_time=None):
        # current_time = datetime.now()
        day_name = current_time.strftime("%a")
        if day_name in ["Tue", "Wed"]:
            # If today is Tuesday or Wednesday, sleep until 9 AM tomorrow
            next_run = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            if current_time >= next_run:
                next_run = next_run.replace(day=current_time.day + 1)
            sleep_seconds = (next_run - current_time).total_seconds()
        else:
            # If today is Thursday, sleep until 9 AM on the next Tuesday
            days_ahead = {
                'Mon': 1,
                'Thu':5,
                'Fri': 4, 
                'Sat': 3,
                'Sun': 2
            }.get(day_name)
            next_run = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            next_run = next_run + timedelta(days=days_ahead)
            sleep_seconds = (next_run - current_time).total_seconds()
        logger.info("Trading day is over, sleeping until next trading day at 9 AM")
        time.sleep(sleep_seconds)
            
        
    def rest(self,current_time=None,function=None, sleep_seconds=None):
        did_rest = False
        
        if function is None:
            time.sleep(sleep_seconds)
        else:
            sleep_seconds = function(current_time)
            while sleep_seconds is not None:
                did_rest = True
                
                time.sleep(sleep_seconds)
                current_time = datetime.now()
                sleep_second = function(current_time)
                
        return did_rest    
                
    def _is_market_open(self,current_time):
        us_market = mcal.get_calendar("Capital_Markets_US")
        today = current_time.date()
        schedule = us_market.schedule(start_date=today, end_date=today)
        answer = us_market.is_open_now(schedule)
        if answer:
            return True
        else:
            logger.info("Market is closed. Not trading.")
            return False
    
    def _early_market_close(self,current_time):
        try:
            us_market = mcal.get_calendar("Capital_Markets_US")
            today = current_time.date()
            schedule = us_market.schedule(start_date=today, end_date=today)
            if schedule.empty:
                return False
            early_closes = us_market.early_closes(schedule)
            
            is_early_close = not early_closes.empty
            
            if is_early_close:
                logger.info("Market has early closing hours today. Not trading.")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error checking early market close: {e}")
            return False
    
    def _check_beg_end_of_month(self, current_time):
        # Check if today is the first or last day of the month
        if current_time.day in CALENDAR_DAY_NOT_TO_TRADE:
            # Calculate time until next business day at 9 AM
            next_run = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            next_run = next_run + timedelta(days=1)
            while next_run.day in CALENDAR_DAY_NOT_TO_TRADE:
                next_run = next_run + timedelta(days=1)
            sleep_seconds = (next_run - current_time).total_seconds()
            logger.info("Today is in the window of not trading. Sleeping...")
            return sleep_seconds
        else:
            return None
    
    def _check_day_of_week_to_trade(self, current_time):
        day_name = current_time.strftime("%a")
        if day_name not in ["Tue", "Wed", "Thu"]:
            #for when it's Monday, Friday, Saturday or Sunday
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
            logger.info("Today is not a weekday that is allowed to trade. Sleeping...")
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
            logger.info("Right now is no longer in the hours allowed to trade. Sleeping...")
            return sleep_seconds
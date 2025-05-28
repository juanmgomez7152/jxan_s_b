import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from typing import Dict, List, Optional


class YahooFinanceScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.base_url = "https://finance.yahoo.com"
        
    def get_most_active_stocks(self) -> Optional[pd.DataFrame]:
        """
        Scrapes the most active stocks from Yahoo Finance
        
        Returns:
            DataFrame containing most active stocks data or None if an error occurs
        """
        url = f"{self.base_url}/markets/stocks/most-active/"
        
        try:
            # Add random delay to avoid being blocked
            time.sleep(random.uniform(1, 3))
            
            # Send request
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find the script containing trending tickers JSON
            script_tag = soup.find('script', {'id': 'fin-trending-tickers'})
            
            if not script_tag:
                print("Could not find trending tickers data")
                return None
                
            # Extract and parse the JSON data
            import json
            stocks_data = json.loads(script_tag.string)
            
            # Convert to DataFrame
            df = pd.DataFrame(stocks_data)
            
            # Extract relevant columns and normalize nested JSON values
            result = []
            for stock in stocks_data:
                result.append({
                    'Symbol': stock['symbol'],
                    'Company': stock['shortName'],
                    'Price': stock['regularMarketPrice']['fmt'] if 'fmt' in stock['regularMarketPrice'] else stock['regularMarketPrice'],
                    'Change': stock['regularMarketChangePercent']['fmt'] if 'fmt' in stock['regularMarketChangePercent'] else stock['regularMarketChangePercent'],
                    'Exchange': stock['exchange']
                })
            
            # Create DataFrame from the processed data
            df_final = pd.DataFrame(result)
            
            # Take top 20 stocks
            df_final = df_final.head(20)
            result_list = df_final['Symbol'].tolist()
            return result_list
                
        except requests.exceptions.RequestException as e:
            print(f"Error making request: {e}")
            return None
        except Exception as e:
            print(f"Error scraping data: {e}")
            return None
    
    def save_to_csv(self, df: pd.DataFrame, filename: str = "app/resources/most_active_stocks.csv") -> bool:
        """
        Save DataFrame to CSV file
        
        Args:
            df: DataFrame to save
            filename: Name of the output CSV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            df.to_csv(filename, index=False)
            print(f"Data saved to {filename}")
            return True
        except Exception as e:
            print(f"Error saving data: {e}")
            return False
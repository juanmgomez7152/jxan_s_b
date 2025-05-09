from app.agent import AIStockAgent
import logging

ai_stock_agent = AIStockAgent()
# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # controller_schwab()
    ai_stock_agent.run_ai_agent()
    
if __name__ == "__main__":
    
    main()
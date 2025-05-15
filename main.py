from app.agent import AIStockAgent
import logging
import asyncio

ai_stock_agent = AIStockAgent()
logging.getLogger("httpx").setLevel(logging.WARNING)   # Suppresses HTTP client logs
logging.getLogger("openai").setLevel(logging.WARNING)  # Suppresses OpenAI client logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    asyncio.run(ai_stock_agent.run_ai_agent())
    
if __name__ == "__main__":
    
    main()
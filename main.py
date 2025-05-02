from app.schwab_services import controller_schwab
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    controller_schwab()
    
if __name__ == "__main__":
    
    main()
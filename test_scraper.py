import logging
from scraper import scrape_dutchie_dispensary_direct
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_scraper():
    test_url = "https://dutchie.com/dispensary/mission-catonsville"
    logger.info(f"Testing scraper with URL: {test_url}")
    
    results = scrape_dutchie_dispensary_direct(test_url)
    
    if results:
        logger.info(f"Successfully scraped {len(results[0]['products'])} products")
        logger.info("\nFirst 3 products:")
        for i, product in enumerate(results[0]['products'][:3], 1):
            logger.info(f"\nProduct {i}:")
            for key, value in product.items():
                logger.info(f"  {key}: {value}")
    else:
        logger.error("No results found")

if __name__ == "__main__":
    test_scraper() 
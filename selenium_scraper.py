from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import logging
import json
from typing import List, Dict, Optional
from datetime import datetime
import time
import requests
import re
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DutchieScraper:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
            
            # Set Chrome binary location
            chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            if os.path.exists(chrome_path):
                chrome_options.binary_location = chrome_path
                logger.info(f"Using Chrome from: {chrome_path}")
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            # Execute CDP commands to prevent detection
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                """
            })
            
            logger.info("Chrome driver setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {str(e)}")
            raise
    
    def get_dispensary_id(self, url: str) -> Optional[str]:
        """Extract dispensary ID from the page"""
        try:
            logger.info(f"Loading URL: {url}")
            self.driver.get(url)
            logger.info("Waiting for page to load...")
            time.sleep(5)  # Wait for page to load
            
            # First try: Extract from URL
            # Example: https://dutchie.com/dispensary/mission-catonsville
            dispensary_name = url.split("/")[-1]
            if dispensary_name:
                logger.info(f"Using dispensary name from URL: {dispensary_name}")
                return dispensary_name
            
            # Second try: Look for dispensary ID in the page source
            logger.info("Getting page source...")
            page_source = self.driver.page_source
            logger.info(f"Page source length: {len(page_source)}")
            
            # Try to find dispensary ID in script tags
            logger.info("Searching for dispensary ID...")
            script_pattern = r'"dispensaryId":\s*"([^"]+)"'
            match = re.search(script_pattern, page_source)
            if match:
                dispensary_id = match.group(1)
                logger.info(f"Found dispensary ID using primary pattern: {dispensary_id}")
                return dispensary_id
            
            # Try alternate pattern
            logger.info("Trying alternate pattern...")
            alt_pattern = r'"retailerId":\s*"([^"]+)"'
            match = re.search(alt_pattern, page_source)
            if match:
                dispensary_id = match.group(1)
                logger.info(f"Found dispensary ID using alternate pattern: {dispensary_id}")
                return dispensary_id
            
            logger.error("No dispensary ID found in page source")
            # Save page source for debugging
            with open("dutchie_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            logger.info("Saved page source to dutchie_page_source.html for debugging")
            return None
            
        except Exception as e:
            logger.error(f"Error getting dispensary ID: {str(e)}")
            return None
    
    def fetch_menu_data(self, dispensary_id: str) -> List[Dict]:
        """Fetch menu data using GraphQL API"""
        try:
            url = "https://dutchie.com/graphql"
            logger.info(f"Making GraphQL request to {url}")
            
            # GraphQL query for menu data
            query = """
            query MenuQuery($dispensaryId: ID!, $menuType: MenuType!) {
                menu(dispensaryId: $dispensaryId, menuType: $menuType) {
                    products {
                        id
                        name
                        description
                        image
                        category
                        variants {
                            option
                            priceRec
                            quantity
                        }
                    }
                }
            }
            """
            
            # Request headers
            headers = {
                'content-type': 'application/json',
                'apollographql-client-name': 'dutchie-plus',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
            }
            logger.info("Using headers: %s", headers)
            
            # Variables for the query
            variables = {
                "dispensaryId": dispensary_id,
                "menuType": "RECREATIONAL"  # Can be RECREATIONAL or MEDICAL
            }
            logger.info("Using variables: %s", variables)
            
            # Make the request
            logger.info("Sending GraphQL request...")
            response = requests.post(
                url,
                headers=headers,
                json={
                    "query": query,
                    "variables": variables
                }
            )
            
            if response.status_code != 200:
                logger.error(f"GraphQL request failed with status code: {response.status_code}")
                logger.error(f"Response content: {response.text}")
                return []
            
            logger.info("Successfully received GraphQL response")
            data = response.json()
            logger.debug("Response data: %s", data)
            
            if 'data' in data and 'menu' in data['data'] and 'products' in data['data']['menu']:
                products = []
                for product in data['data']['menu']['products']:
                    # Get the lowest price from variants
                    price = None
                    if product.get('variants'):
                        prices = [v.get('priceRec') for v in product['variants'] if v.get('priceRec')]
                        if prices:
                            price = min(prices)
                    
                    products.append({
                        'name': product.get('name'),
                        'price': price,
                        'description': product.get('description'),
                        'image': product.get('image'),
                        'category': product.get('category')
                    })
                logger.info(f"Successfully processed {len(products)} products from GraphQL response")
                return products
            
            logger.error("No products found in GraphQL response structure")
            logger.debug("Response structure: %s", data)
            return []
            
        except Exception as e:
            logger.error(f"Error fetching menu data: {str(e)}")
            return []
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()

def scrape_dutchie_dispensary(url: str) -> List[Dict]:
    """
    Scrape a Dutchie dispensary website
    
    Args:
        url: The dispensary website URL
    
    Returns:
        List of scraped products
    """
    scraper = None
    try:
        logger.info(f"Starting to scrape URL: {url}")
        scraper = DutchieScraper(headless=True)
        
        # Get dispensary ID
        logger.info("Attempting to get dispensary ID...")
        dispensary_id = scraper.get_dispensary_id(url)
        if not dispensary_id:
            logger.error("Could not find dispensary ID")
            return []
        logger.info(f"Found dispensary ID: {dispensary_id}")
        
        # Fetch menu data
        logger.info("Fetching menu data from GraphQL API...")
        products = scraper.fetch_menu_data(dispensary_id)
        
        if not products:
            logger.error("No products found in the API response")
            return []
        logger.info(f"Successfully fetched {len(products)} products")
        
        # Return in the format expected by the FastAPI endpoint
        result = [{
            "url": url,
            "products": products,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }]
        logger.info("Successfully formatted response")
        return result
        
    except Exception as e:
        logger.error(f"Error in scrape_dutchie_dispensary: {str(e)}")
        return []
    finally:
        if scraper:
            logger.info("Closing browser...")
            scraper.close()

if __name__ == "__main__":
    # Configure logging to show more details
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Test the scraper
    test_url = "https://dutchie.com/dispensary/mission-catonsville"
    logger.info(f"Testing scraper with URL: {test_url}")
    results = scrape_dutchie_dispensary(test_url)
    
    if results:
        logger.info(f"Successfully scraped {len(results[0]['products'])} products")
        print("\nFirst 5 products:")
        for product in results[0]['products'][:5]:
            print("\nProduct:")
            for key, value in product.items():
                print(f"{key}: {value}")
    else:
        logger.error("No results found") 
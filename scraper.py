import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.exceptions import CloseSpider
from scrapy.http import Request
from typing import List, Dict, Optional
import logging
import json
from datetime import datetime
from proxy_manager import proxy_manager
from scrapy import signals
import requests

logger = logging.getLogger(__name__)

class DispensarySpider(CrawlSpider):
    name = "dispensary"
    start_urls = []
    custom_settings = {
        'ROBOTSTXT_OBEY': False,  # Dutchie blocks via robots.txt
        'CONCURRENT_REQUESTS': 2,
        'DOWNLOAD_DELAY': 5,
        'COOKIES_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
        },
        'DEFAULT_REQUEST_HEADERS': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }
    }

    def __init__(
        self, 
        start_urls: List[str] = None, 
        allowed_domains: List[str] = None,
        max_pages: int = 10,
        product_selectors: Dict[str, str] = None,
        *args, 
        **kwargs
    ):
        self.items = []
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls or []
        self.allowed_domains = allowed_domains or [self._get_domain(url) for url in self.start_urls]
        self.max_pages = max_pages
        self.pages_crawled = 0
        
        # Dutchie-specific selectors
        self.product_selectors = {
            'name': '[data-test-id="product-title"]::text, .ProductTitle::text, h1::text',
            'price': '[data-test-id="product-price"]::text, .ProductPrice::text, [data-price]::text',
            'description': '[data-test-id="product-description"]::text, .ProductDescription::text',
            'image': '[data-test-id="product-image"]::attr(src), .ProductImage::attr(src)',
            'category': '[data-test-id="product-category"]::text, .ProductCategory::text'
        }
        if product_selectors:
            self.product_selectors.update(product_selectors)
        
        # Define crawling rules for Dutchie
        self.rules = (
            Rule(
                LinkExtractor(
                    allow=(r'.*/menu.*', r'.*/product/.*'),
                    deny=(r'.*/cart.*', r'.*/search.*', r'.*/account.*', r'.*/login.*')
                ),
                callback='parse_item',
                follow=True,
                process_request='process_request'
            ),
        )
        
        # Initialize CrawlSpider rules
        super()._compile_rules()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def start_requests(self):
        """Start requests with rotating headers and proxies"""
        for url in self.start_urls:
            metadata = proxy_manager.get_request_metadata()
            headers = metadata['headers']
            headers.update({
                'Referer': 'https://dutchie.com/',
                'Origin': 'https://dutchie.com'
            })
            yield Request(
                url=url,
                dont_filter=True,
                headers=headers,
                meta={
                    'proxy': metadata['proxies'].get('http') if metadata['proxies'] else None,
                    'handle_httpstatus_list': [403, 404, 429, 500, 502, 503],
                    'max_retry_times': 5
                },
                errback=self.errback_httpbin,
                callback=self.parse_start_url
            )

    def errback_httpbin(self, failure):
        """Handle request failures"""
        logger.error(f"Request failed: {str(failure.value)}")
        return None

    def parse_start_url(self, response):
        """Parse the initial URL"""
        if response.status == 403:
            logger.warning("Access forbidden - might need to adjust headers or use different proxy")
            return None
        if response.status == 429:
            logger.warning("Rate limited - backing off")
            return None
        return self.parse_item(response)

    def process_request(self, request, spider):
        """Process request before sending"""
        metadata = proxy_manager.get_request_metadata()
        request.headers.update(metadata['headers'])
        if metadata['proxies']:
            request.meta['proxy'] = metadata['proxies'].get('http')
        return request

    def parse_item(self, response):
        """Parse product information from the page"""
        try:
            self.pages_crawled += 1
            if self.pages_crawled > self.max_pages:
                raise CloseSpider(f'Reached maximum number of pages: {self.max_pages}')

            products = []
            # Look for product containers
            product_containers = response.css('.product, .product-item, [data-product-id], article.product')
            
            if not product_containers:
                # If no containers found, treat the page as a single product
                product_data = self._extract_product_data(response)
                if product_data:
                    products.append(product_data)
            else:
                # Extract data from each product container
                for container in product_containers:
                    product_data = self._extract_product_data(container)
                    if product_data:
                        products.append(product_data)

            if products:
                item = {
                    'url': response.url,
                    'timestamp': datetime.now().isoformat(),
                    'products': products,
                    'status': 'success'
                }
                self.items.append(item)  # Store the item
                return item
            else:
                logger.warning(f"No products found on page: {response.url}")
                return {
                    'url': response.url,
                    'timestamp': datetime.now().isoformat(),
                    'products': [],
                    'status': 'no_products_found'
                }

        except Exception as e:
            logger.error(f"Error parsing page {response.url}: {str(e)}")
            return {
                'url': response.url,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'status': 'error'
            }

    def _extract_product_data(self, selector) -> Optional[Dict]:
        """Extract product data using configured selectors"""
        product = {}
        
        for field, css_selector in self.product_selectors.items():
            # Try multiple selectors for each field
            for selector_variant in css_selector.split(','):
                selector_variant = selector_variant.strip()
                value = selector.css(selector_variant).get()
                if value:
                    product[field] = value.strip()
                    break
        
        # Only return product if we found at least some data
        return product if product else None

def scrape_dutchie_dispensary_direct(url: str) -> List[Dict]:
    """
    Scrape a Dutchie dispensary using their GraphQL API directly
    
    Args:
        url: The dispensary website URL
    
    Returns:
        List of scraped products
    """
    try:
        # Create a session to maintain cookies
        session = requests.Session()
        
        # Extract dispensary name from URL
        dispensary_name = url.split("/")[-1]
        logger.info(f"Extracted dispensary name from URL: {dispensary_name}")
        if not dispensary_name:
            logger.error("Could not extract dispensary name from URL")
            return []
            
        # GraphQL endpoint
        graphql_url = "https://dutchie.com/graphql"
        logger.info(f"Using GraphQL endpoint: {graphql_url}")
        
        # First, visit the dispensary page to get cookies
        logger.info(f"Visiting dispensary page to get cookies: {url}")
        response = session.get(url)
        logger.info(f"Initial page visit status code: {response.status_code}")
        logger.info(f"Cookies after initial visit: {dict(session.cookies)}")
        
        # Query to get retailer ID
        retailer_query = """
        query RetailerByUrlName($urlName: String!) {
            retailerByUrlName(urlName: $urlName) {
                id
                name
                menuTypes
                address {
                    city
                    state
                }
            }
        }
        """
        logger.info("Using retailer query: %s", retailer_query.strip())
        
        # Headers
        headers = {
            'content-type': 'application/json',
            'apollographql-client-name': 'dutchie-plus',
            'apollographql-client-version': '2024.02',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://dutchie.com',
            'Referer': url,
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }
        logger.info("Using headers: %s", headers)
        
        # Get retailer ID
        logger.info(f"Getting retailer ID for {dispensary_name}")
        request_data = {
            "query": retailer_query,
            "variables": {
                "urlName": dispensary_name
            }
        }
        logger.info("Request data: %s", json.dumps(request_data, indent=2))
        
        response = session.post(
            graphql_url,
            headers=headers,
            json=request_data
        )
        
        logger.info(f"Retailer ID request status code: {response.status_code}")
        logger.info(f"Retailer ID response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get retailer ID: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return []
            
        data = response.json()
        logger.info("Retailer ID response data: %s", json.dumps(data, indent=2))
        
        if not data.get('data', {}).get('retailerByUrlName', {}).get('id'):
            logger.error("No retailer ID found in response")
            return []
            
        retailer_id = data['data']['retailerByUrlName']['id']
        menu_types = data['data']['retailerByUrlName']['menuTypes']
        logger.info(f"Found retailer ID: {retailer_id}")
        logger.info(f"Available menu types: {menu_types}")
        
        # Query for menu data
        menu_query = """
        query Menu($retailerId: ID!, $menuType: MenuType!) {
            menu(retailerId: $retailerId, menuType: $menuType) {
                products {
                    id
                    name
                    description
                    image
                    category
                    brand {
                        name
                    }
                    effects
                    potencyThc {
                        formatted
                    }
                    potencyCbd {
                        formatted
                    }
                    strainType
                    variants {
                        id
                        option
                        priceRec
                        specialPriceRec
                        quantity
                        soldOut
                    }
                }
            }
        }
        """
        logger.info("Using menu query: %s", menu_query.strip())
        
        # Get menu data
        logger.info("Getting menu data")
        menu_type = "RECREATIONAL" if "RECREATIONAL" in menu_types else "MEDICAL"
        logger.info(f"Selected menu type: {menu_type}")
        
        request_data = {
            "query": menu_query,
            "variables": {
                "retailerId": retailer_id,
                "menuType": menu_type
            }
        }
        logger.info("Menu request data: %s", json.dumps(request_data, indent=2))
        
        response = session.post(
            graphql_url,
            headers=headers,
            json=request_data
        )
        
        logger.info(f"Menu request status code: {response.status_code}")
        logger.info(f"Menu response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get menu data: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return []
            
        data = response.json()
        logger.info("Menu response data: %s", json.dumps(data, indent=2))
        
        if not data.get('data', {}).get('menu', {}).get('products'):
            logger.error("No products found in menu data")
            return []
            
        # Process products
        products = []
        for product in data['data']['menu']['products']:
            # Get the lowest price from variants
            price = None
            special_price = None
            in_stock = False
            if product.get('variants'):
                prices = [v.get('priceRec') for v in product['variants'] if v.get('priceRec')]
                special_prices = [v.get('specialPriceRec') for v in product['variants'] if v.get('specialPriceRec')]
                if prices:
                    price = min(prices)
                if special_prices:
                    special_price = min(special_prices)
                # Check if any variant is in stock
                in_stock = any(not v.get('soldOut', True) for v in product['variants'])
                
            products.append({
                'name': product.get('name'),
                'price': special_price if special_price else price,
                'original_price': price if special_price else None,
                'description': product.get('description'),
                'image': product.get('image'),
                'category': product.get('category'),
                'brand': product.get('brand', {}).get('name'),
                'effects': product.get('effects', []),
                'thc': product.get('potencyThc', {}).get('formatted'),
                'cbd': product.get('potencyCbd', {}).get('formatted'),
                'strain_type': product.get('strainType'),
                'in_stock': in_stock
            })
            
        logger.info(f"Successfully processed {len(products)} products")
        return [{
            'url': url,
            'products': products,
            'timestamp': datetime.now().isoformat(),
            'status': 'success'
        }]
        
    except Exception as e:
        logger.error(f"Error in scrape_dutchie_dispensary_direct: {str(e)}")
        logger.exception("Full traceback:")
        return []

def scrape_dispensary(
    url: str,
    output_file: str = None,
    max_pages: int = 10,
    custom_selectors: Dict[str, str] = None,
    proxies: List[str] = None
) -> List[Dict]:
    """
    Scrape a dispensary website
    
    Args:
        url: The dispensary website URL
        output_file: Optional JSON file to save results
        max_pages: Maximum number of pages to crawl
        custom_selectors: Custom CSS selectors for product data
        proxies: List of proxy servers to use
    
    Returns:
        List of scraped products
    """
    try:
        # Check if it's a Dutchie URL
        if "dutchie.com" in url.lower():
            return scrape_dutchie_dispensary_direct(url)
        
        # For other websites, use the original Scrapy implementation
        # Update proxy list if provided
        if proxies:
            proxy_manager.proxies = proxies
            if proxy_manager.check_proxy_health:
                proxy_manager._check_all_proxies()
        
        # Configure crawler settings
        settings = {
            'LOG_LEVEL': 'INFO',
            'FEEDS': {
                output_file: {'format': 'json'} if output_file else None
            }
        }
        
        # Initialize crawler process
        process = CrawlerProcess(settings)
        
        # Configure spider
        spider_settings = {
            'start_urls': [url],
            'max_pages': max_pages,
            'product_selectors': custom_selectors
        }
        
        # Add spider to crawler
        process.crawl(DispensarySpider, **spider_settings)
        
        # Store results in memory
        results = []
        
        # Override the spider's closed signal to capture items
        def store_items(spider):
            nonlocal results
            results.extend(spider.items)
        
        # Add closed callback
        for crawler in process.crawlers:
            crawler.signals.connect(store_items, signals.spider_closed)
        
        # Run the spider
        process.start()
        
        # Return results
        return results if results else []
        
    except Exception as e:
        logger.error(f"Error in scrape_dispensary: {str(e)}")
        return []

# Example usage:
if __name__ == "__main__":
    # Example custom selectors for a specific dispensary
    custom_selectors = {
        'name': '.product-name::text',
        'price': '.product-price::text',
        'description': '.product-desc::text',
        'image': '.product-image::attr(src)',
        'category': '.product-category::text'
    }
    
    # Example proxies (replace with your actual proxies)
    example_proxies = [
        "http://proxy1.example.com:8080",
        "http://proxy2.example.com:8080"
    ]
    
    results = scrape_dispensary(
        url="https://example-dispensary.com",
        output_file="products.json",
        max_pages=5,
        custom_selectors=custom_selectors,
        proxies=example_proxies
    ) 
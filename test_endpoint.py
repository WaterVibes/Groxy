import requests
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_endpoint():
    url = "http://127.0.0.1:8000/dispensary/https://dutchie.com/dispensary/mission-catonsville"
    try:
        logger.info(f"Making request to: {url}")
        response = requests.get(url)
        logger.info(f"Status Code: {response.status_code}")
        
        logger.info("Response Headers:")
        logger.info(json.dumps(dict(response.headers), indent=2))
        
        if response.status_code == 200:
            data = response.json()
            logger.info("\nResponse Summary:")
            logger.info(f"Status: {data.get('status')}")
            logger.info(f"Total Products: {data.get('total_products', 0)}")
            logger.info(f"Cache Hit: {data.get('cache_hit', False)}")
            logger.info(f"Timestamp: {data.get('timestamp')}")
            
            if data.get('products'):
                logger.info(f"\nFirst 3 Products:")
                for i, product in enumerate(data['products'][:3], 1):
                    logger.info(f"\nProduct {i}:")
                    logger.info(f"  Name: {product.get('name')}")
                    if product.get('brand'):
                        logger.info(f"  Brand: {product.get('brand')}")
                    if product.get('price'):
                        if product.get('original_price'):
                            logger.info(f"  Price: ${product.get('price')} (was ${product.get('original_price')})")
                        else:
                            logger.info(f"  Price: ${product.get('price')}")
                    else:
                        logger.info("  Price: Not available")
                    logger.info(f"  Category: {product.get('category')}")
                    logger.info(f"  Strain Type: {product.get('strain_type')}")
                    if product.get('thc'):
                        logger.info(f"  THC: {product.get('thc')}")
                    if product.get('cbd'):
                        logger.info(f"  CBD: {product.get('cbd')}")
                    if product.get('effects'):
                        logger.info(f"  Effects: {', '.join(product.get('effects'))}")
                    logger.info(f"  In Stock: {product.get('in_stock', False)}")
                    if product.get('description'):
                        logger.info(f"  Description: {product.get('description')[:100]}...")
            else:
                logger.warning("No products found in response")
        else:
            logger.error("\nError Response:")
            logger.error(json.dumps(response.json(), indent=2))
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    test_endpoint() 
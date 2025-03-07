import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_dutchie_api():
    # Dutchie GraphQL endpoint
    url = "https://dutchie.com/graphql"
    
    # Query for menu data
    query = """
    query MenuQuery($dispensaryId: ID!, $menuType: MenuType!) {
        menu(dispensaryId: $dispensaryId, menuType: $menuType) {
            products {
                id
                name
                description
                image
                category
                priceRec
                variants {
                    id
                    option
                    priceMed
                    priceRec
                    quantity
                }
            }
        }
    }
    """
    
    # Headers based on browser inspection
    headers = {
        'content-type': 'application/json',
        'apollographql-client-name': 'dutchie-plus',
        'Accept': '*/*',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    # Try to get dispensary ID first
    try:
        # First, get the dispensary details
        dispensary_url = "https://dutchie.com/dispensary/mission-catonsville"
        response = requests.get(dispensary_url, headers=headers)
        logger.info(f"Initial response status: {response.status_code}")
        logger.info("Response headers:")
        logger.info(json.dumps(dict(response.headers), indent=2))
        
        # Look for dispensary ID in response
        content = response.text
        logger.info(f"Response length: {len(content)}")
        logger.info("First 1000 characters of response:")
        logger.info(content[:1000])
        
    except Exception as e:
        logger.error(f"Error inspecting Dutchie API: {str(e)}")

if __name__ == "__main__":
    inspect_dutchie_api() 
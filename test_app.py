import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app
from scraper import DispensarySpider
from proxy_manager import ProxyManager
from cache import InMemoryCache
import json

# Mock Redis and use in-memory cache for testing
@pytest.fixture(autouse=True)
def mock_redis():
    with patch('cache.RedisCache') as mock:
        mock.side_effect = Exception("Redis not available")
        yield mock

@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client

def test_root_endpoint(test_client):
    """Test the root endpoint"""
    response = test_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "service" in data
    assert "version" in data
    assert data["cache_status"] == "connected"

def test_dispensary_endpoint(test_client):
    """Test the dispensary endpoint with a test URL"""
    test_url = "example-dispensary.com/menu"
    response = test_client.get(f"/dispensary/{test_url}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "products" in data
    assert "total_products" in data
    assert "timestamp" in data

def test_proxy_manager():
    """Test proxy manager functionality"""
    # Initialize with test proxies
    test_proxies = ["http://test-proxy:8080"]
    pm = ProxyManager(proxies=test_proxies, check_proxy_health=False)
    
    # Test user agent generation
    user_agent = pm.get_random_user_agent()
    assert isinstance(user_agent, str)
    assert len(user_agent) > 0
    
    # Test request metadata
    metadata = pm.get_request_metadata()
    assert "headers" in metadata
    assert "User-Agent" in metadata["headers"]
    assert "proxies" in metadata

def test_products_endpoint(test_client):
    """Test the products endpoint with filters"""
    test_url = "example-dispensary.com/menu"
    response = test_client.get(
        f"/dispensary/{test_url}/products",
        params={
            "category": "flower",
            "min_price": 10,
            "max_price": 100
        }
    )
    assert response.status_code == 200
    products = response.json()
    assert isinstance(products, list)

def test_cache_operations():
    """Test in-memory cache operations"""
    cache = InMemoryCache()
    
    # Test cache data
    assert cache.cache_data("test_key", {"data": "test"}, ttl=60) == True
    
    # Test get cached data
    cached = cache.get_cached_data("test_key")
    assert cached == {"data": "test"}
    
    # Test delete cached data
    assert cache.delete_cached_data("test_key") == True
    assert cache.get_cached_data("test_key") is None
    
    # Test clear cache
    assert cache.clear_cache() == True

if __name__ == "__main__":
    pytest.main(["-v", __file__]) 
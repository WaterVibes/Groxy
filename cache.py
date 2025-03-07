from typing import Any, Optional, Union
import redis
import json
from datetime import timedelta
import logging
from functools import wraps
from collections import OrderedDict
import time
import os

logger = logging.getLogger(__name__)

# Environment variables for Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_SSL = os.getenv("REDIS_SSL", "false").lower() == "true"
REDIS_SSL_CERT_REQS = os.getenv("REDIS_SSL_CERT_REQS", "none")
USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"

class InMemoryCache:
    """Simple in-memory cache implementation with TTL support"""
    def __init__(self, max_size: int = 1000):
        self.cache = OrderedDict()
        self.max_size = max_size
        logger.info("Initialized in-memory cache")
        
    def cache_data(self, key: str, data: Any, ttl: Union[int, timedelta] = 300) -> bool:
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            # Remove oldest item if cache is full
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
                
            expires_at = time.time() + ttl
            self.cache[key] = (data, expires_at)
            return True
        except Exception as e:
            logger.error(f"Error caching data for key {key}: {str(e)}")
            return False
            
    def get_cached_data(self, key: str, default: Any = None) -> Optional[Any]:
        try:
            if key not in self.cache:
                return default
                
            data, expires_at = self.cache[key]
            if time.time() > expires_at:
                del self.cache[key]
                return default
                
            return data
        except Exception as e:
            logger.error(f"Error retrieving cached data for key {key}: {str(e)}")
            return default
            
    def delete_cached_data(self, key: str) -> bool:
        try:
            if key in self.cache:
                del self.cache[key]
            return True
        except Exception as e:
            logger.error(f"Error deleting cached data for key {key}: {str(e)}")
            return False
            
    def clear_cache(self, pattern: str = "*") -> bool:
        try:
            self.cache.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False

class RedisCache:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        socket_timeout: int = 5,
        ssl: bool = False,
        ssl_cert_reqs: Optional[str] = None
    ):
        """Initialize Redis cache connection"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                password=password,
                username="default",
                decode_responses=True,
                socket_timeout=socket_timeout,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Successfully connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis at {host}:{port}: {str(e)}")
            raise

    def cache_data(
        self,
        key: str,
        data: Any,
        ttl: Union[int, timedelta] = 300
    ) -> bool:
        """
        Cache data in Redis
        
        Args:
            key: Cache key
            data: Data to cache (will be JSON serialized)
            ttl: Time to live in seconds or timedelta object
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert timedelta to seconds if needed
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
                
            # Serialize data to JSON
            serialized_data = json.dumps(data)
            
            # Store in Redis with TTL
            return bool(self.redis_client.setex(key, ttl, serialized_data))
            
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error caching data for key {key}: {str(e)}")
            return False

    def get_cached_data(
        self,
        key: str,
        default: Any = None
    ) -> Optional[Any]:
        """
        Retrieve cached data from Redis
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached data if found and valid JSON, otherwise default
        """
        try:
            cached = self.redis_client.get(key)
            if cached is None:
                return default
                
            return json.loads(cached)
            
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving cached data for key {key}: {str(e)}")
            return default

    def delete_cached_data(self, key: str) -> bool:
        """Delete cached data for a key"""
        try:
            return bool(self.redis_client.delete(key))
        except redis.RedisError as e:
            logger.error(f"Error deleting cached data for key {key}: {str(e)}")
            return False

    def clear_cache(self, pattern: str = "*") -> bool:
        """Clear all cached data matching pattern"""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return bool(self.redis_client.delete(*keys))
            return True
        except redis.RedisError as e:
            logger.error(f"Error clearing cache with pattern {pattern}: {str(e)}")
            return False

def cache_response(ttl: Union[int, timedelta] = 300):
    """
    Decorator for caching FastAPI endpoint responses
    
    Usage:
        @app.get("/data")
        @cache_response(ttl=300)
        async def get_data():
            return {"data": "expensive operation"}
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Use default cache instance
            if default_cache is None:
                # If no cache is available, just execute the function
                return await func(*args, **kwargs)
            
            # Generate cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Try to get cached response
            cached_response = default_cache.get_cached_data(cache_key)
            if cached_response is not None:
                return cached_response
            
            # If not cached, execute function
            response = await func(*args, **kwargs)
            
            # Cache the response
            default_cache.cache_data(cache_key, response, ttl)
            
            return response
        return wrapper
    return decorator

# Create default cache instance
if USE_REDIS:
    try:
        default_cache = RedisCache(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            ssl=REDIS_SSL,
            ssl_cert_reqs=REDIS_SSL_CERT_REQS
        )
        logger.info("Successfully initialized Redis cache")
    except redis.ConnectionError as e:
        logger.warning(f"Redis connection failed ({str(e)}), falling back to in-memory cache")
        default_cache = InMemoryCache()
else:
    logger.info("Using in-memory cache (Redis not enabled)")
    default_cache = InMemoryCache()

# Convenience functions using default cache instance
def cache_data(key: str, data: Any, ttl: Union[int, timedelta] = 300) -> bool:
    """Convenience function for caching data using default cache instance"""
    if default_cache is None:
        return False
    return default_cache.cache_data(key, data, ttl)

def get_cached_data(key: str, default: Any = None) -> Optional[Any]:
    """Convenience function for retrieving cached data using default cache instance"""
    if default_cache is None:
        return default
    return default_cache.get_cached_data(key, default) 
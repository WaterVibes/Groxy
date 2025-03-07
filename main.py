from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from scraper import scrape_dispensary
from cache import RedisCache, InMemoryCache, cache_response
import logging
import redis
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="GrassApp Proxy Server",
    description="A standardized API for fetching and caching dispensary data",
    version="1.0.0"
)

# Initialize cache with fallback
USE_REDIS = os.getenv("USE_REDIS", "false").lower() == "true"

if USE_REDIS:
    try:
        cache = RedisCache(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD")
        )
        logger.info("Successfully initialized Redis cache")
    except redis.ConnectionError as e:
        logger.warning(f"Redis connection failed ({str(e)}), falling back to in-memory cache")
        cache = InMemoryCache()
else:
    logger.info("Using in-memory cache (Redis not enabled)")
    cache = InMemoryCache()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data Models
class Product(BaseModel):
    """Product data model"""
    id: Optional[str] = None
    name: str
    price: Optional[float] = None
    original_price: Optional[float] = None
    description: Optional[str] = None
    image_url: Optional[HttpUrl] = Field(None, alias='image')
    category: Optional[str] = None
    brand: Optional[str] = None
    effects: List[str] = Field(default_factory=list)
    thc: Optional[str] = None
    cbd: Optional[str] = None
    strain_type: Optional[str] = None
    in_stock: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DispensaryResponse(BaseModel):
    """Standardized dispensary response"""
    status: str = "success"
    url: str
    products: List[Product]
    total_products: int
    timestamp: datetime
    cache_hit: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ErrorResponse(BaseModel):
    """Standardized error response"""
    status: str = "error"
    code: int
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

# Error handler for HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.status_code,
            "message": str(exc.detail),
            "timestamp": datetime.now().isoformat()
        }
    )

# Generic error handler
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": f"Internal server error: {str(exc)}",
            "timestamp": datetime.now().isoformat()
        }
    )

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "success",
        "service": "GrassApp Proxy Server",
        "version": "1.0.0",
        "cache_status": "connected" if cache else "disabled",
        "timestamp": datetime.now()
    }

@app.get("/dispensary/{dispensary_url:path}", response_model=DispensaryResponse)
@cache_response(ttl=timedelta(minutes=30))
async def get_dispensary_data(
    dispensary_url: str,
    max_pages: Optional[int] = Query(5, ge=1, le=20),
    force_refresh: bool = False,
    include_metadata: bool = False
):
    """
    Fetch and standardize dispensary data
    
    Args:
        dispensary_url: The URL of the dispensary
        max_pages: Maximum number of pages to scrape (1-20)
        force_refresh: Force fresh data fetch
        include_metadata: Include additional metadata in response
    """
    try:
        # Generate cache key
        cache_key = f"dispensary:{dispensary_url}:{max_pages}"
        
        # Try to get from cache if not forcing refresh
        if not force_refresh:
            cached_data = cache.get_cached_data(cache_key)
            if cached_data:
                logger.info(f"Cache hit for {dispensary_url}")
                return DispensaryResponse(**cached_data)
        
        # Ensure URL starts with https://
        if not dispensary_url.startswith(('http://', 'https://')):
            dispensary_url = f"https://{dispensary_url}"
        
        logger.info(f"Scraping data from {dispensary_url}")
        
        # Scrape fresh data
        scraped_data = scrape_dispensary(
            url=dispensary_url,
            max_pages=max_pages
        )
        
        if not scraped_data:
            logger.error(f"No data returned from scraper for {dispensary_url}")
            raise HTTPException(
                status_code=404,
                detail="No data found for this dispensary"
            )
        
        # Standardize product data
        products = []
        for item in scraped_data:
            try:
                if isinstance(item, dict) and 'products' in item:
                    # Handle nested product data
                    for product in item['products']:
                        try:
                            products.append(Product(
                                name=product.get("name", "Unknown Product"),
                                price=float(product.get("price", 0.0)) if product.get("price") else None,
                                description=product.get("description"),
                                image_url=product.get("image"),
                                category=product.get("category"),
                                metadata={
                                    k: v for k, v in product.items()
                                    if k not in ["name", "price", "description", "image", "category"]
                                } if include_metadata else {}
                            ))
                        except ValueError as e:
                            logger.warning(f"Skipping invalid product: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"Error processing scraped item: {str(e)}")
                continue
        
        # Create standardized response
        response = DispensaryResponse(
            url=dispensary_url,
            products=products,
            total_products=len(products),
            timestamp=datetime.now(),
            cache_hit=False,
            metadata={
                "max_pages": max_pages,
                "pages_scraped": len(scraped_data)
            } if include_metadata else {}
        )
        
        # Cache the response
        if products:
            cache.cache_data(cache_key, response.dict(), ttl=timedelta(minutes=30))
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing dispensary data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=500,
                message=f"Failed to process dispensary data: {str(e)}"
            ).dict()
        )

@app.get("/dispensary/{dispensary_url:path}/products", response_model=List[Product])
async def get_dispensary_products(
    dispensary_url: str,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None
):
    """
    Get filtered products from a dispensary
    
    Args:
        dispensary_url: The URL of the dispensary
        category: Filter by product category
        min_price: Minimum price filter
        max_price: Maximum price filter
        in_stock: Filter by stock status
    """
    try:
        # Get full dispensary data
        response = await get_dispensary_data(dispensary_url)
        products = response.products
        
        # Apply filters
        if category:
            products = [p for p in products if p.category and category.lower() in p.category.lower()]
        if min_price is not None:
            products = [p for p in products if p.price and p.price >= min_price]
        if max_price is not None:
            products = [p for p in products if p.price and p.price <= max_price]
        if in_stock is not None:
            products = [p for p in products if p.in_stock == in_stock]
            
        return products
        
    except Exception as e:
        logger.error(f"Error filtering products: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=500,
                message=f"Failed to filter products: {str(e)}"
            ).dict()
        )

@app.post("/cache/clear")
async def clear_cache(pattern: str = "*"):
    """Clear the Redis cache"""
    try:
        success = cache.clear_cache(pattern)
        return {
            "status": "success" if success else "error",
            "message": f"Cache cleared with pattern: {pattern}",
            "timestamp": datetime.now()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                code=500,
                message=f"Failed to clear cache: {str(e)}"
            ).dict()
        ) 
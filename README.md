# GrassApp Proxy Server

A standardized API for fetching and caching dispensary data, with a focus on Dutchie integration.

## Features

- Direct GraphQL API integration with Dutchie
- Selenium-based scraping fallback
- Redis caching support with in-memory fallback
- Proxy rotation and management
- Comprehensive product data including:
  - Prices (regular and special)
  - Brand information
  - THC and CBD content
  - Strain types and effects
  - Stock status
- FastAPI-based REST endpoints
- Automatic Chrome driver management
- Detailed logging and error handling

## Requirements

- Python 3.8+
- Chrome browser installed
- Redis (optional, for production caching)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/proxyga.git
cd proxyga
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (optional):
```bash
# Redis configuration (optional)
export REDIS_HOST=your-redis-host
export REDIS_PORT=your-redis-port
export REDIS_PASSWORD=your-redis-password
export REDIS_SSL=true
export USE_REDIS=true
```

## Usage

### Starting the Server

Run the FastAPI server:
```bash
python run.py
```

The server will start on `http://localhost:8000` by default.

### API Endpoints

#### 1. Health Check
```
GET /
```
Returns service status and version information.

#### 2. Fetch Dispensary Data
```
GET /dispensary/{dispensary_url}
```
Parameters:
- `dispensary_url`: URL-encoded dispensary URL
- `max_pages` (optional): Maximum number of pages to scrape (1-20)
- `force_refresh` (optional): Force fresh data fetch
- `include_metadata` (optional): Include additional metadata

#### 3. Filter Products
```
GET /dispensary/{dispensary_url}/products
```
Parameters:
- `category`: Filter by product category
- `min_price`: Minimum price filter
- `max_price`: Maximum price filter
- `in_stock`: Filter by stock status

#### 4. Clear Cache
```
POST /cache/clear
```
Parameter:
- `pattern`: Cache key pattern to clear (default: "*")

### Example Usage

```python
import requests

# Fetch dispensary data
url = "http://localhost:8000/dispensary/https://dutchie.com/dispensary/example-dispensary"
response = requests.get(url)
data = response.json()

# Filter products
filtered_url = f"{url}/products?category=flower&min_price=10&max_price=100"
filtered = requests.get(filtered_url)
products = filtered.json()
```

## Testing

Run the test suite:
```bash
python -m pytest test_app.py
```

Individual component tests:
```bash
python test_scraper.py     # Test scraper functionality
python test_selenium.py    # Test Selenium setup
python test_endpoint.py    # Test API endpoint
```

## Error Handling

The API returns standardized error responses:
```json
{
    "status": "error",
    "code": 500,
    "message": "Error description",
    "timestamp": "2024-03-14T12:00:00"
}
```

## Caching

- Redis is recommended for production use
- Automatic fallback to in-memory cache if Redis is unavailable
- Default cache TTL: 30 minutes
- Configurable through environment variables

## Security

- Rate limiting through proxy rotation
- User-Agent rotation
- Automatic handling of anti-bot measures
- Secure header management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
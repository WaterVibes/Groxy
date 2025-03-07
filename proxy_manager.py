import random
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import requests
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manages proxy and user agent rotation with health checks"""
    
    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        user_agents: Optional[List[str]] = None,
        check_proxy_health: bool = True
    ):
        self.proxies = proxies or []
        self.healthy_proxies = set()
        self.unhealthy_proxies = set()
        self.proxy_health_checks = {}
        self.check_proxy_health = check_proxy_health
        
        # Initialize User-Agent generator
        try:
            self.ua = UserAgent()
            self._use_fake_ua = True
        except Exception as e:
            logger.warning(f"Could not initialize fake-useragent: {e}. Using fallback user agents.")
            self._use_fake_ua = False
            
        # Fallback User-Agents
        self.user_agents = user_agents or [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 17_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ]
        
        if proxies and check_proxy_health:
            self._check_all_proxies()

    def _check_proxy_health(self, proxy: str) -> bool:
        """Check if a proxy is working"""
        try:
            # Test proxy with a simple request
            test_url = "https://httpbin.org/ip"
            response = requests.get(
                test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Proxy health check failed for {proxy}: {str(e)}")
            return False

    def _check_all_proxies(self):
        """Check health of all proxies"""
        for proxy in self.proxies:
            if self._check_proxy_health(proxy):
                self.healthy_proxies.add(proxy)
                self.proxy_health_checks[proxy] = datetime.now()
            else:
                self.unhealthy_proxies.add(proxy)

    def get_random_user_agent(self) -> str:
        """Get a random user agent"""
        if self._use_fake_ua:
            return self.ua.random
        return random.choice(self.user_agents)

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random healthy proxy"""
        if not self.proxies:
            return None
            
        # Recheck unhealthy proxies periodically
        current_time = datetime.now()
        for proxy in list(self.unhealthy_proxies):
            last_check = self.proxy_health_checks.get(proxy)
            if not last_check or current_time - last_check > timedelta(minutes=30):
                if self._check_proxy_health(proxy):
                    self.unhealthy_proxies.remove(proxy)
                    self.healthy_proxies.add(proxy)
                self.proxy_health_checks[proxy] = current_time

        # Get a random healthy proxy
        if self.healthy_proxies:
            proxy = random.choice(list(self.healthy_proxies))
            return {"http": proxy, "https": proxy}
            
        # If no healthy proxies, try any proxy
        if self.proxies:
            proxy = random.choice(self.proxies)
            return {"http": proxy, "https": proxy}
            
        return None

    def get_request_metadata(self) -> Dict:
        """Get headers and proxy for a request"""
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }
        
        return {
            "headers": headers,
            "proxies": self.get_random_proxy()
        }

# Example proxy list (replace with your actual proxies)
DEFAULT_PROXIES = [
    # Format: "protocol://username:password@host:port"
    # Free proxy example (not recommended for production):
    # "http://public-proxy-host:8080"
    
    # Paid proxy examples:
    # "http://username:password@premium-proxy.com:8080",
    # "socks5://username:password@socks-proxy.com:1080"
]

# Create default instance
proxy_manager = ProxyManager(
    proxies=DEFAULT_PROXIES,
    check_proxy_health=True
) 
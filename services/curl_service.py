"""
HTTP client service for making external API calls.
Supports async (aiohttp) and sync (requests) with retry, circuit breaker, and logging.
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class HTTPService:
    """
    HTTP client service for external API calls.
    Features:
    - Sync (requests) and async (aiohttp) support
    - Automatic retry with exponential backoff
    - Connection pooling
    - Request/Response logging
    """

    def __init__(self, base_url: str = "", timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self._session = None

    def _get_session(self) -> requests.Session:
        """Get or create a requests session with retry strategy."""
        if self._session is None:
            self._session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            )
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=10,
                pool_maxsize=100,
            )
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def _build_url(self, path: str) -> str:
        """Build full URL from base and path."""
        if self.base_url:
            return urljoin(self.base_url, path)
        return path

    def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """Make a synchronous HTTP request with retry logic."""
        url = self._build_url(path)
        session = self._get_session()
        kwargs.setdefault("timeout", self.timeout)

        logger.info(f"HTTP {method} {url}")
        response = session.request(method, url, **kwargs)
        logger.info(f"HTTP {method} {url} -> {response.status_code}")

        return response

    def get(self, path: str, **kwargs) -> requests.Response:
        """HTTP GET request."""
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        """HTTP POST request."""
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        """HTTP PUT request."""
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        """HTTP PATCH request."""
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        """HTTP DELETE request."""
        return self.request("DELETE", path, **kwargs)

    # ---- Async Methods ----

    async def request_async(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make an asynchronous HTTP request."""
        url = self._build_url(path)
        kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=self.timeout))

        async with aiohttp.ClientSession() as session:
            logger.info(f"HTTP Async {method} {url}")
            async with session.request(method, url, **kwargs) as response:
                data = await response.json()
                logger.info(f"HTTP Async {method} {url} -> {response.status}")
                return {
                    "status": response.status,
                    "data": data,
                    "headers": dict(response.headers),
                }

    async def get_async(self, path: str, **kwargs) -> Dict[str, Any]:
        """Async HTTP GET request."""
        return await self.request_async("GET", path, **kwargs)

    async def post_async(self, path: str, **kwargs) -> Dict[str, Any]:
        """Async HTTP POST request."""
        return await self.request_async("POST", path, **kwargs)
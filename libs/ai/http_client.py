"""
Generic HTTP (curl-style) client for arbitrary AI endpoints.

Use this when the backend is not Ollama — e.g. an internal REST service that
requires custom authentication headers. Kept separate from ``OllamaClient``
so the two backends can evolve independently.

Usage::

    client = GenericCurlClient(base_url="https://ai.internal.example.com/api")
    response = client.post_json("/chat", payload={"q": "hi"},
                                headers={"X-Api-Key": "..."})

    for chunk in client.post_json_stream("/chat", payload, headers=...):
        ...  # each parsed JSON line / SSE data frame
"""

import json
from typing import Any, Dict, Generator, Optional

import requests

from libs.ai.errors import AIServiceError, AIServiceTimeout, AIServiceUnavailable

DEFAULT_TIMEOUT = 300


class GenericCurlClient:
    """Reusable JSON-over-HTTP client with custom header support."""

    def __init__(self, base_url: str, timeout: Optional[int] = None,
                 default_headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.default_headers = dict(default_headers or {})

    def _request(self, method: str, path: str, payload: Optional[Dict[str, Any]],
                 headers: Optional[Dict[str, str]], stream: bool = False):
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        merged = {**self.default_headers, **(headers or {})}
        try:
            return requests.request(
                method, url, json=payload, headers=merged, stream=stream, timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise AIServiceTimeout(f"Request timed out after {self.timeout}s: {url}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise AIServiceUnavailable(f"Cannot reach AI endpoint: {url}") from exc
        except requests.exceptions.RequestException as exc:
            raise AIServiceError(f"AI request failed: {exc}") from exc

    @staticmethod
    def _raise_for_error(response) -> None:
        if response.ok:
            return
        try:
            detail = json.dumps(response.json())[:500]
        except ValueError:
            detail = (response.text or "")[:500]
        raise AIServiceError(f"AI endpoint returned HTTP {response.status_code}: {detail}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_json(self, path: str, payload: Dict[str, Any],
                  headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """POST JSON and return the parsed response body."""
        response = self._request("POST", path, payload, headers, stream=False)
        self._raise_for_error(response)
        try:
            return response.json()
        except ValueError as exc:
            raise AIServiceError("AI endpoint returned non-JSON body") from exc

    def get_json(self, path: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """GET and return the parsed response body."""
        response = self._request("GET", path, None, headers, stream=False)
        self._raise_for_error(response)
        try:
            return response.json()
        except ValueError as exc:
            raise AIServiceError("AI endpoint returned non-JSON body") from exc

    def post_json_stream(
        self,
        path: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        data_key: str = "response",
    ) -> Generator[str, None, None]:
        """POST JSON and stream newline-delimited JSON responses.

        Yields the value of ``data_key`` from each JSON line (matches both
        Ollama's ``{"response": "..."}`` and OpenAI-style ``delta`` objects
        can be adapted via ``data_key``).
        """
        response = self._request("POST", path, payload, headers, stream=True)
        self._raise_for_error(response)
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line or line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    line = line[len("data: "):]
                if line.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if isinstance(data, dict):
                    if data.get("error"):
                        raise AIServiceError(f"AI stream error: {data['error']}")
                    nested = data.get("message")
                    if isinstance(nested, dict) and nested.get("content"):
                        yield nested["content"]
                        continue
                    content = data.get(data_key, "")
                    if content:
                        yield content
        except requests.exceptions.RequestException as exc:
            raise AIServiceError(f"AI stream interrupted: {exc}") from exc
        finally:
            response.close()

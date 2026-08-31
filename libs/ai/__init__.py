"""
Reusable AI backend clients.

- ``OllamaClient``     — native Ollama API (/api/chat, streaming)
- ``GenericCurlClient``— any curl-style JSON endpoint with custom headers
"""

from libs.ai.errors import AIServiceError, AIServiceTimeout, AIServiceUnavailable
from libs.ai.http_client import GenericCurlClient
from libs.ai.ollama_client import OllamaClient

__all__ = [
    "AIServiceError",
    "AIServiceTimeout",
    "AIServiceUnavailable",
    "GenericCurlClient",
    "OllamaClient",
]

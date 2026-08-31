"""
AI service exceptions.
"""


class AIServiceError(Exception):
    """Base error for AI service calls."""


class AIServiceTimeout(AIServiceError):
    """The AI backend did not respond within the configured timeout."""


class AIServiceUnavailable(AIServiceError):
    """The AI backend is unreachable (connection refused, DNS failure...)."""

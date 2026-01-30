"""LLM client package.

This package provides clients for different LLM providers:
- GLM (智谱AI): Cost-effective filtering
- Claude: High-quality resume tailoring (to be implemented)
"""

from .base import BaseLLMClient, LLMResponse, LLMError, RateLimitError, APIError, InvalidResponseError, TailoredResume
from .glm_client import GLMClient, FilterResult
from .claude_client import ClaudeClient

__all__ = [
    "BaseLLMClient",
    "LLMResponse",
    "LLMError",
    "RateLimitError",
    "APIError",
    "InvalidResponseError",
    "GLMClient",
    "FilterResult",
    "ClaudeClient",
    "TailoredResume",
]

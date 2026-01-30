"""OpenRouter API client (unified gateway)."""

import os
from typing import Optional
from openai import AsyncOpenAI

from .openai_client import OpenAIClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenRouterClient(OpenAIClient):
    """OpenRouter API client.
    
    Uses OpenAI-compatible API to access 100+ models.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-3-sonnet"
    ):
        """Initialize OpenRouter client.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model ID (e.g., "anthropic/claude-3-sonnet")
        """
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        
        # Initialize base OpenAI client but override client instance
        # We don't call super().__init__ because we need to pass base_url
        self.api_key = api_key
        self.base_url = self.BASE_URL
        self.total_cost = 0.0
        self.total_tokens = {"input": 0, "output": 0}
        
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
            default_headers={"HTTP-Referer": "https://github.com/YourDaddyy/Job_Hunter_AI"}
        )
        logger.info(f"Initialized OpenRouter client with model: {model}")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost (Placeholder).
        
        OpenRouter has dynamic pricing per model.
        For now, we return 0.0 or implement specific widely used models.
        """
        # TODO: Implement dynamic pricing lookup from OpenRouter API
        return 0.0

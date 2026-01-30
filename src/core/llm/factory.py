"""LLM Factory for creating provider clients."""

from typing import Optional, Literal, Dict, Type
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger
from .base import BaseLLMClient
from .glm_client import GLMClient
from .claude_client import ClaudeClient
from .openai_client import OpenAIClient
from .gemini_client import GeminiClient
from .openrouter_client import OpenRouterClient

logger = get_logger(__name__)

LLMPurpose = Literal["filter", "tailor"]


class LLMFactory:
    """Factory for creating LLM clients based on configuration."""

    _clients: Dict[str, Type[BaseLLMClient]] = {
        "glm": GLMClient,
        "claude": ClaudeClient,
        "openai": OpenAIClient,
        "gemini": GeminiClient,
        "openrouter": OpenRouterClient,
    }

    @classmethod
    def create_client(
        cls,
        purpose: LLMPurpose,
        config_loader: Optional[ConfigLoader] = None
    ) -> BaseLLMClient:
        """Create LLM client for specified purpose.

        Args:
            purpose: "filter" or "tailor"
            config_loader: Optional config loader (uses default if None)

        Returns:
            Configured LLM client instance

        Raises:
            ValueError: If provider not supported
        """
        config_loader = config_loader or ConfigLoader()
        
        try:
            providers = config_loader.get_llm_providers()
            llm_config = providers.get_config(purpose)
            
            if not llm_config:
                # Fallback defaults if config missing (shouldn't happen with default logic)
                logger.warning(f"No config found for purpose '{purpose}', using GLM default")
                return GLMClient(model="glm-4-flash")
                
            provider_name = llm_config.provider.lower()
            model = llm_config.model

            if provider_name not in cls._clients:
                available = list(cls._clients.keys())
                error_msg = f"Unknown provider: {provider_name}. Available: {available}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            client_class = cls._clients[provider_name]
            logger.info(f"Creating {provider_name} client for {purpose} (model: {model})")
            
            return client_class(model=model)
            
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            raise

    @classmethod
    def register_client(
        cls,
        name: str,
        client_class: Type[BaseLLMClient]
    ) -> None:
        """Register a new LLM client type."""
        cls._clients[name.lower()] = client_class
        logger.info(f"Registered new LLM provider: {name}")

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available provider names."""
        return list(cls._clients.keys())

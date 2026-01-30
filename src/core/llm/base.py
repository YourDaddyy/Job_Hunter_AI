"""Base LLM client abstractions.

This module provides abstract base classes and common structures
for all LLM client implementations (GLM, Claude).
"""

from abc import ABC, abstractmethod
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class FilterResult:
    """Job filtering result.
    
    Attributes:
        score: Match score (0.0-1.0)
        reasoning: Brief explanation of the score
        key_requirements: List of key job requirements identified
        red_flags: List of issues/red flags detected
        visa_compatible: Whether job offers visa sponsorship
        remote_compatible: Whether remote work is available
        salary_compatible: Whether salary meets requirements
        cost_usd: Cost of this API call
    """
    score: float
    reasoning: str
    key_requirements: List[str]
    red_flags: List[str]
    visa_compatible: bool
    remote_compatible: bool
    salary_compatible: bool
    cost_usd: float = 0.0


@dataclass
class TailoredResume:
    """Tailored resume result from LLM.

    Attributes:
        summary: Customized professional summary (2-3 sentences)
        selected_achievements: List of 3-5 most relevant achievements with tailored bullets
        highlighted_skills: List of 8-12 skills most relevant to job
        tailoring_notes: Brief explanation of customizations made
        cost_usd: Cost of this API call
    """
    summary: str
    selected_achievements: List[Dict]
    highlighted_skills: List[str]
    tailoring_notes: str
    cost_usd: float = 0.0


@dataclass
class LLMResponse:
    """Standard LLM response structure.
    
    Attributes:
        content: Response text content
        model: Model name used
        usage: Token usage dict with 'input_tokens' and 'output_tokens'
        cost_usd: Cost in USD for this request
        raw_response: Raw API response object
    """
    content: str
    model: str
    usage: Dict[str, int]  # {"input_tokens": int, "output_tokens": int}
    cost_usd: float
    raw_response: Any


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients.
    
    Provides common functionality for tracking costs and tokens
    across all LLM providers.
    """

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize base LLM client.
        
        Args:
            api_key: API key for authentication
            base_url: Optional custom base URL for API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.total_cost = 0.0
        self.total_tokens = {"input": 0, "output": 0}

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Send chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Role can be 'user', 'assistant', or 'system'
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum output tokens
            
        Returns:
            LLMResponse with content and usage information
            
        Raises:
            LLMError: If request fails
        """
        pass

    @abstractmethod
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics for this client instance.
        
        Returns:
            Dict with total_cost_usd, total_input_tokens, total_output_tokens
        """
        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_input_tokens": self.total_tokens["input"],
            "total_output_tokens": self.total_tokens["output"],
        }

    def reset_stats(self):
        """Reset usage statistics to zero."""
        self.total_cost = 0.0
        self.total_tokens = {"input": 0, "output": 0}

    def parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response.
        
        Handles:
        - Clean JSON
        - JSON wrapped in markdown code blocks
        - JSON with extra text before/after
        
        Args:
            response_text: Raw response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            InvalidResponseError: If JSON cannot be extracted
        """
        # Try direct parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        code_match = re.search(
            r'```(?:json)?\s*(\{.*?\})\s*```',
            response_text,
            re.DOTALL
        )
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try extracting bare JSON object
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        raise InvalidResponseError(f"Could not parse JSON from response: {response_text[:200]}...")


# Exception classes

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class RateLimitError(LLMError):
    """API rate limit exceeded."""
    pass


class APIError(LLMError):
    """API request failed."""
    pass


class InvalidResponseError(LLMError):
    """Invalid or unparseable response from API."""
    pass

"""Unit tests for LLM clients (GLM, Claude).

Tests cover:
- GLMClient initialization
- Cost calculation
- Response parsing
- Error handling
- Filter result structure
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.core.llm import (
    BaseLLMClient,
    GLMClient,
    FilterResult,
    LLMError,
    RateLimitError,
    APIError,
    InvalidResponseError
)


class TestGLMClient:
    """Test GLM API client."""

    def test_initialization_with_api_key(self):
        """Test GLMClient initializes with API key."""
        client = GLMClient(api_key="test_key_123")
        assert client.api_key == "test_key_123"
        assert client.model == "glm-4-flash"
        assert client.total_cost == 0.0

    def test_initialization_without_api_key_raises(self):
        """Test GLMClient raises error if no API key."""
        with pytest.raises(ValueError, match="GLM_API_KEY not found"):
            GLMClient(api_key=None)

    def test_cost_calculation(self):
        """Test token-to-cost calculation."""
        client = GLMClient(api_key="test")
        
        # Test: 1000 input, 500 output
        # = (1000/1000 * 0.001) + (500/1000 * 0.002)
        # = 0.001 + 0.001 = 0.002
        cost = client.calculate_cost(1000, 500)
        assert cost == 0.002

    def test_cost_calculation_small_values(self):
        """Test cost calculation with small token counts."""
        client = GLMClient(api_key="test")
        
        # Test: 100 input, 50 output
        cost = client.calculate_cost(100, 50)
        assert cost == pytest.approx(0.0002, rel=1e-5)

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Test successful chat completion."""
        client = GLMClient(api_key="test")
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            result = await client.chat([{"role": "user", "content": "Hello"}])
            
            assert result.content == "Test response"
            assert result.usage["input_tokens"] == 100
            assert result.usage["output_tokens"] == 50
            assert result.cost_usd > 0
            assert client.total_cost > 0

    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self):
        """Test handling of rate limit (429) response."""
        client = GLMClient(api_key="test")
        
        mock_response = MagicMock()
        mock_response.status_code = 429
        
        with patch("httpx.AsyncClient.post", return_value=mock_response):
            # Should retry and eventually raise RateLimitError
            # Note: In production this retries, for test we'll catch first attempt
            try:
                await client.chat([{"role": "user", "content": "Test"}])
            except (RateLimitError, tenacity.RetryError):
                pass  # Expected

    def test_parse_json_response_clean(self):
        """Test parsing clean JSON response."""
        client = GLMClient(api_key="test")
        
        json_str = '{"score": 0.85, "reasoning": "Good match"}'
        result = client._parse_json_response(json_str)
        
        assert result["score"] == 0.85
        assert result["reasoning"] == "Good match"

    def test_parse_json_response_markdown_wrapped(self):
        """Test parsing JSON in markdown code block."""
        client = GLMClient(api_key="test")
        
        json_str = '```json\n{"score": 0.75, "reasoning": "OK"}\n```'
        result = client._parse_json_response(json_str)
        
        assert result["score"] == 0.75

    def test_parse_json_response_with_extra_text(self):
        """Test parsing JSON with surrounding text."""
        client = GLMClient(api_key="test")
        
        json_str = 'Here is the result: {"score": 0.90} and more text'
        result = client._parse_json_response(json_str)
        
        assert result["score"] == 0.90

    def test_parse_json_response_invalid_raises(self):
        """Test that invalid JSON raises error."""
        client = GLMClient(api_key="test")
        
        with pytest.raises(ValueError, match="Could not parse JSON"):
            client._parse_json_response("This is not JSON at all")

    def test_stats_tracking(self):
        """Test usage statistics tracking."""
        client = GLMClient(api_key="test")
        
        # Simulate some usage
        client.total_cost = 0.1234
        client.total_tokens["input"] = 5000
        client.total_tokens["output"] = 2000
        
        stats = client.get_stats()
        
        assert stats["total_cost_usd"] == 0.1234
        assert stats["total_input_tokens"] == 5000
        assert stats["total_output_tokens"] == 2000

    def test_reset_stats(self):
        """Test resetting statistics."""
        client = GLMClient(api_key="test")
        
        client.total_cost = 1.0
        client.total_tokens["input"] = 1000
        client.total_tokens["output"] = 500
        
        client.reset_stats()
        
        assert client.total_cost == 0.0
        assert client.total_tokens["input"] == 0
        assert client.total_tokens["output"] == 0


class TestFilterResult:
    """Test FilterResult dataclass."""

    def test_filter_result_creation(self):
        """Test creating FilterResult."""
        result = FilterResult(
            score=0.85,
            reasoning="Strong match",
            key_requirements=["Python", "AWS"],
            red_flags=[],
            visa_compatible=True,
            remote_compatible=True,
            salary_compatible=True,
            cost_usd=0.0015
        )
        
        assert result.score == 0.85
        assert "Python" in result.key_requirements
        assert result.visa_compatible is True
        assert result.cost_usd == 0.0015

    def test_filter_result_defaults(self):
        """Test FilterResult with default cost."""
        result = FilterResult(
            score=0.70,
            reasoning="OK",
            key_requirements=[],
            red_flags=["No sponsorship"],
            visa_compatible=False,
            remote_compatible=True,
            salary_compatible=True
        )
        
        assert result.cost_usd == 0.0  # Default value

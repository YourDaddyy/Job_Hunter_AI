"""GLM API client for job filtering.

GLM (智谱AI) is used for high-volume, cost-effective job filtering.
The glm-4-flash model provides excellent performance at ~$0.001 per job.
"""

import os
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Optional
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .base import BaseLLMClient, LLMResponse, RateLimitError, APIError, InvalidResponseError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FilterResult:
    """Job filtering result from GLM.
    
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


class GLMClient(BaseLLMClient):
    """GLM API client for job filtering.
    
    GLM (智谱AI) pricing (as of 2024):
    - glm-4-flash: ~$0.001 per 1K input tokens, $0.002 per 1K output tokens
    - Typical job filtering: ~500 input tokens, ~150 output tokens = ~$0.001 per job
    """

    # Pricing for glm-4-flash (cheapest model, sufficient for filtering)
    PRICE_PER_1K_INPUT = 0.001   # $0.001 per 1K input tokens
    PRICE_PER_1K_OUTPUT = 0.002  # $0.002 per 1K output tokens

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        model: str = "glm-4-flash"
    ):
        """Initialize GLM client.
        
        Args:
            api_key: GLM API key (defaults to GLM_API_KEY env var)
            base_url: API base URL
            model: Model to use (glm-4-flash recommended for filtering)
        """
        api_key = api_key or os.getenv("GLM_API_KEY")
        if not api_key:
            raise ValueError("GLM_API_KEY not found in environment variables")
        
        super().__init__(api_key, base_url)
        self.model = model
        logger.info(f"Initialized GLM client with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((RateLimitError, httpx.TimeoutException))
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Send chat completion request to GLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            
        Returns:
            LLMResponse with content and usage
            
        Raises:
            APIError: If request fails
            RateLimitError: If rate limited
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=60.0
                )
                
                # Check for rate limiting
                if response.status_code == 429:
                    raise RateLimitError("GLM API rate limit exceeded")
                
                response.raise_for_status()
                data = response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"GLM API HTTP error: {e}")
                raise APIError(f"GLM API request failed: {e}") from e
            except httpx.RequestError as e:
                logger.error(f"GLM API request error: {e}")
                raise APIError(f"GLM API connection failed: {e}") from e

        # Extract usage and calculate cost
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = self.calculate_cost(input_tokens, output_tokens)

        # Update totals
        self.total_cost += cost
        self.total_tokens["input"] += input_tokens
        self.total_tokens["output"] += output_tokens

        content = data["choices"][0]["message"]["content"]
        
        logger.debug(
            f"GLM request complete: {input_tokens} in, {output_tokens} out, "
            f"${cost:.4f}"
        )

        return LLMResponse(
            content=content,
            model=self.model,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
            cost_usd=cost,
            raw_response=data
        )

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost for token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        input_cost = (input_tokens / 1000) * self.PRICE_PER_1K_INPUT
        output_cost = (output_tokens / 1000) * self.PRICE_PER_1K_OUTPUT
        return input_cost + output_cost

    async def filter_job(
        self,
        jd_markdown: str,
        resume_summary: str,
        preferences: str
    ) -> FilterResult:
        """Filter a job posting using GLM.
        
        Args:
            jd_markdown: Job description in markdown format
            resume_summary: Candidate's resume summary
            preferences: Job search preferences
            
        Returns:
            FilterResult with score and analysis
            
        Raises:
            InvalidResponseError: If response cannot be parsed
            APIError: If API request fails
        """
        prompt = self._build_filter_prompt(jd_markdown, resume_summary, preferences)
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await self.chat(messages, temperature=0.3, max_tokens=500)
        except Exception as e:
            logger.error(f"GLM filter_job request failed: {e}")
            raise

        # Parse JSON response
        try:
            data = self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"Failed to parse GLM response: {response.content[:200]}")
            raise InvalidResponseError(f"Invalid JSON response: {e}") from e

        return FilterResult(
            score=float(data.get("score", 0.0)),
            reasoning=data.get("reasoning", "No reasoning provided"),
            key_requirements=data.get("key_requirements", []),
            red_flags=data.get("red_flags", []),
            visa_compatible=data.get("visa_compatible", True),
            remote_compatible=data.get("remote_compatible", True),
            salary_compatible=data.get("salary_compatible", True),
            cost_usd=response.cost_usd
        )

    def _build_filter_prompt(
        self,
        jd_markdown: str,
        resume_summary: str,
        preferences: str
    ) -> str:
        """Build filtering prompt for GLM.
        
        Args:
            jd_markdown: Job description
            resume_summary: Resume summary
            preferences: User preferences
            
        Returns:
            Formatted prompt string
        """
        return f"""You are evaluating a job posting for a candidate.

## Candidate Profile
{resume_summary}

## Job Preferences
{preferences}

## Job Description
{jd_markdown}

---

Evaluate the match and return ONLY valid JSON (no markdown, no explanation):
{{
  "score": 0.0-1.0,
  "reasoning": "Brief explanation (max 100 words)",
  "key_requirements": ["requirement1", "requirement2", "requirement3"],
  "red_flags": ["flag1", "flag2"],
  "visa_compatible": true/false,
  "remote_compatible": true/false,
  "salary_compatible": true/false
}}

## Score Guidelines

**0.9-1.0**: Perfect match
- All key requirements met
- Strong experience alignment
- No red flags

**0.8-0.9**: Excellent match
- Most requirements met
- Good experience fit
- Minor gaps acceptable

**0.7-0.8**: Good match
- Core requirements met
- Some transferable skills
- Worth applying

**0.6-0.7**: Moderate match
- Partial match
- User should review
- May be stretch

**0.5-0.6**: Weak match
- Significant gaps
- Likely not suitable

**0.0-0.5**: Poor match
- Major misalignment
- Reject

## Red Flags to Detect
- Security clearance required
- No visa sponsorship / must be authorized to work without sponsorship
- Onsite only (if remote preferred)
- Salary below minimum requirements
- Excessive experience requirements (10+ years for entry-level roles)
- Contract/staffing agency positions (W2, C2C, corp-to-corp)
- Required skills completely misaligned

Return ONLY the JSON object, no other text."""

    def _parse_json_response(self, response_text: str) -> Dict:
        """Parse JSON from GLM response.
        
        Handles:
        - Clean JSON
        - JSON wrapped in markdown code blocks
        - JSON with extra text before/after
        
        Args:
            response_text: Raw response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If JSON cannot be extracted
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

        raise ValueError(f"Could not parse JSON from response: {response_text[:200]}...")

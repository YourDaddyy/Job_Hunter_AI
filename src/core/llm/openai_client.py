"""OpenAI API client for job filtering and resume tailoring."""

import os
import json
import re
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .base import BaseLLMClient, LLMResponse, RateLimitError, APIError, InvalidResponseError, TailoredResume
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client.
    
    Attributes:
        PRICE_PER_1K_INPUT: Cost per 1k input tokens (default gpt-4o-mini)
        PRICE_PER_1K_OUTPUT: Cost per 1k output tokens
    """

    PRICING = {
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        """Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-mini)
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        super().__init__(api_key)
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)
        logger.info(f"Initialized OpenAI client with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception) # OpenAI lib raises specific errors, catching broader for now
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """Send chat completion to OpenAI.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            
        Returns:
            LLMResponse
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError(f"OpenAI API rate limit exceeded: {e}") from e
            else:
                raise APIError(f"OpenAI API request failed: {e}") from e

        # Extract usage and calculate cost
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens
        cost = self.calculate_cost(input_tokens, output_tokens)

        # Update totals
        self.total_cost += cost
        self.total_tokens["input"] += input_tokens
        self.total_tokens["output"] += output_tokens

        content = response.choices[0].message.content
        
        logger.debug(
            f"OpenAI request complete: {input_tokens} in, {output_tokens} out, "
            f"${cost:.4f}"
        )

        return LLMResponse(
            content=content,
            model=self.model,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
            cost_usd=cost,
            raw_response=response
        )

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost for token usage."""
        pricing = self.PRICING.get(self.model, self.PRICING["gpt-4o-mini"])
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    async def filter_job(
        self,
        jd_markdown: str,
        resume_summary: str,
        preferences: str
    ): # Return type omitted to avoid circular import of FilterResult for now or duplicate definition
        """Filter job using OpenAI.
        
        Note: Currently duplicating prompt logic from GLMClient. 
        In a future refactor, prompts should be moved to a shared PromptManager.
        """
        # Re-use the same prompt structure for consistency
        # For MVP, we'll implement a simple prompt here
        prompt = f"""You are evaluating a job posting.
        
Candidate: {resume_summary}
Preferences: {preferences}
Job: {jd_markdown}

Evaluate match score (0.0-1.0) and requirements.
Return valid JSON:
{{
  "score": 0.0-1.0,
  "reasoning": "explanation",
  "key_requirements": ["req1", "req2"],
  "red_flags": [],
  "visa_compatible": true,
  "remote_compatible": true,
  "salary_compatible": true
}}"""
        
        response = await self.chat([{"role": "user", "content": prompt}], temperature=0.3)
        return self._parse_json(response.content)

    async def tailor_resume(
        self,
        resume_markdown: str,
        achievements_markdown: str,
        job_title: str,
        job_company: str,
        job_jd: str,
        key_requirements: List[str]
    ) -> TailoredResume:
        """Tailor resume using OpenAI."""
        requirements_list = "\n".join(f"- {req}" for req in key_requirements)
        
        prompt = f"""Tailor this resume for {job_title} at {job_company}.

Job Description:
{job_jd}

Key Requirements:
{requirements_list}

Base Resume:
{resume_markdown}

Achievements:
{achievements_markdown}

Return valid JSON:
{{
  "summary": "tailored summary",
  "selected_achievements": [{{ "name": "...", "bullets": ["..."] }}],
  "highlighted_skills": ["..."],
  "tailoring_notes": "..."
}}"""

        response = await self.chat([{"role": "user", "content": prompt}], temperature=0.5)
        data = self._parse_json(response.content)
        
        return TailoredResume(
            summary=data.get("summary", ""),
            selected_achievements=data.get("selected_achievements", []),
            highlighted_skills=data.get("highlighted_skills", []),
            tailoring_notes=data.get("tailoring_notes", ""),
            cost_usd=response.cost_usd
        )

    def _parse_json(self, text: str) -> Dict:
        """Parse JSON from response."""
        try:
            # Try finding JSON block
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return json.loads(text)
        except Exception:
             # Fallback simple extraction
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise InvalidResponseError("Could not parse JSON")

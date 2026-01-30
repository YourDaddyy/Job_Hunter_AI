"""Claude API client for resume tailoring.

Claude (Anthropic) is used for high-quality resume customization.
The claude-sonnet-4 model provides excellent creative writing for summaries
and achievement selection at ~$0.01-0.02 per resume.
"""

import os
import json
import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from anthropic import AsyncAnthropic
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
class TailoredResume:
    """Tailored resume result from Claude.
    
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


class ClaudeClient(BaseLLMClient):
    """Claude API client for resume tailoring.
    
    Claude Sonnet 4 pricing:
    - Input: ~$0.003 per 1K tokens
    - Output: ~$0.015 per 1K tokens
    - Typical resume tailoring: ~1,200 input + ~600 output = ~$0.013 per resume
    """

    # Pricing for Claude Sonnet 4
    PRICE_PER_1K_INPUT = 0.003   # $3 per 1M input tokens
    PRICE_PER_1K_OUTPUT = 0.015  # $15 per 1M output tokens

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """Initialize Claude client.
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model to use (claude-sonnet-4-20250514 recommended)
        """
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        super().__init__(api_key)
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key)
        logger.info(f"Initialized Claude client with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(RateLimitError)
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        system: Optional[str] = None
    ) -> LLMResponse:
        """Send chat completion request to Claude.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            system: Optional system prompt (separate from messages in Claude API)
            
        Returns:
            LLMResponse with content and usage
            
        Raises:
            APIError: If request fails
            RateLimitError: If rate limited
        """
        # Convert messages format - extract system if in messages
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                formatted_messages.append(msg)
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "",
                messages=formatted_messages,
                temperature=temperature,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str:
                raise RateLimitError(f"Claude API rate limit exceeded: {e}") from e
            else:
                raise APIError(f"Claude API request failed: {e}") from e

        # Extract usage and calculate cost
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self.calculate_cost(input_tokens, output_tokens)

        # Update totals
        self.total_cost += cost
        self.total_tokens["input"] += input_tokens
        self.total_tokens["output"] += output_tokens

        content = response.content[0].text
        
        logger.debug(
            f"Claude request complete: {input_tokens} in, {output_tokens} out, "
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

    async def tailor_resume(
        self,
        resume_markdown: str,
        achievements_markdown: str,
        job_title: str,
        job_company: str,
        job_jd: str,
        key_requirements: List[str]
    ) -> TailoredResume:
        """Tailor resume for a specific job using Claude.
        
        Args:
            resume_markdown: Base resume in markdown format
            achievements_markdown: Achievement pool in markdown format
            job_title: Target job title
            job_company: Target company name
            job_jd: Job description markdown
            key_requirements: List of key requirements from filtering
            
        Returns:
            TailoredResume with customized content
            
        Raises:
            InvalidResponseError: If response cannot be parsed
            APIError: If API request fails
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            resume_markdown,
            achievements_markdown,
            job_title,
            job_company,
            job_jd,
            key_requirements
        )
        
        messages = [{"role": "user", "content": user_prompt}]
        
        try:
            response = await self.chat(
                messages,
                temperature=0.5,
                max_tokens=2000,
                system=system_prompt
            )
        except Exception as e:
            logger.error(f"Claude tailor_resume request failed: {e}")
            raise

        # Parse JSON response
        try:
            data = self._parse_json_response(response.content)
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {response.content[:200]}")
            raise InvalidResponseError(f"Invalid JSON response: {e}") from e

        return TailoredResume(
            summary=data.get("summary", ""),
            selected_achievements=data.get("selected_achievements", []),
            highlighted_skills=data.get("highlighted_skills", []),
            tailoring_notes=data.get("tailoring_notes", ""),
            cost_usd=response.cost_usd
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt for resume tailoring."""
        return """You are an expert resume writer specializing in technical roles.
Your task is to tailor a resume for a specific job posting.

Guidelines:
1. Match keywords from the job description naturally
2. Prioritize recent and relevant experience
3. Quantify achievements with numbers when possible
4. Use action verbs (led, built, implemented, achieved)
5. Keep bullets concise (1-2 lines each)
6. Ensure ATS compatibility (no tables, simple formatting)
7. Total resume should fit on 1-2 pages

Do NOT:
- Fabricate experience or skills
- Use generic buzzwords without context
- Include irrelevant achievements
- Exceed what's actually in the base resume"""

    def _build_user_prompt(
        self,
        resume_markdown: str,
        achievements_markdown: str,
        job_title: str,
        job_company: str,
        job_jd: str,
        key_requirements: List[str]
    ) -> str:
        """Build user prompt for tailoring."""
        requirements_list = "\n".join(f"- {req}" for req in key_requirements) if key_requirements else "- Not specified"
        
        return f"""## Target Job
Title: {job_title}
Company: {job_company}

Key Requirements (from filtering):
{requirements_list}

## Job Description
{job_jd}

---

## Base Resume
{resume_markdown}

---

## Achievement Pool
{achievements_markdown}

---

## Instructions

1. **Summary**: Write a 2-3 sentence professional summary tailored to this role.
   - Highlight relevant experience and skills
   - Include keywords from the job description
   - Be specific about years of experience and expertise areas

2. **Achievements**: Select 3-5 most relevant achievements from the pool.
   - Choose based on keyword match and relevance
   - Tailor bullet points to use job description language
   - Quantify results where possible

3. **Skills**: List 8-12 skills most relevant to this role.
   - Prioritize skills mentioned in the job description
   - Include both technical and soft skills
   - Order by relevance

Return ONLY valid JSON (no markdown, no explanation):
{{
  "summary": "Tailored professional summary",
  "selected_achievements": [
    {{
      "name": "achievement name",
      "company": "Company Name",
      "period": "2022 - Present",
      "bullets": [
        "Tailored bullet point 1",
        "Tailored bullet point 2"
      ]
    }}
  ],
  "highlighted_skills": ["skill1", "skill2"],
  "tailoring_notes": "Brief explanation of customizations made"
}}"""

    def _parse_json_response(self, response_text: str) -> Dict:
        """Parse JSON from Claude response.
        
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

        # Try extracting bare JSON object (handle nested objects)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON from response: {response_text[:200]}...")

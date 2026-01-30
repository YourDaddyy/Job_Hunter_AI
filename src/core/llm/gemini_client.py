"""Gemini API client for job filtering and resume tailoring."""

import os
import json
import re
from typing import List, Dict, Optional
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from .base import BaseLLMClient, LLMResponse, RateLimitError, APIError, InvalidResponseError, TailoredResume
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(BaseLLMClient):
    """Google Gemini API client.
    
    Attributes:
        PRICE_PER_1K_INPUT: Cost per 1k input tokens
        PRICE_PER_1K_OUTPUT: Cost per 1k output tokens
    """

    PRICING = {
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004}, # Estimated, very cheap
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp"
    ):
        """Initialize Gemini client.
        
        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            model: Model to use (default: gemini-2.0-flash-exp)
        """
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        super().__init__(api_key)
        self.model = model
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)
        logger.info(f"Initialized Gemini client with model: {model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception)
    )
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """Send chat completion to Gemini.
        
        Args:
            messages: List of message dicts. 
                     Gemini uses different format (history=[{'role':,'parts':}]), 
                     so we need to convert.
            temperature: Sampling temperature
            max_tokens: Maximum output tokens
            
        Returns:
            LLMResponse
        """
        # Convert messages to Gemini format
        # System instructions should be set at model init, but for simplicity we'll prepend to prompt
        # Multi-turn chat
        history = []
        last_message = ""
        
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg["content"]
            
            if msg["role"] == "system":
                # Prepend system prompt to first user message if possible, or just treat as logic
                # For chat history, we'll strip system role or prepend
                last_message = f"System Instruction: {content}\n\n" + last_message
            elif msg == messages[-1] and msg["role"] == "user":
                last_message += content
            else:
                history.append({"role": role, "parts": [content]})

        try:
            chat = self.client.start_chat(history=history)
            
            response = await chat.send_message_async(
                last_message,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens
                ),
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
        except Exception as e:
            error_str = str(e).lower()
            if "quota" in error_str or "429" in error_str:
                raise RateLimitError(f"Gemini API rate limit exceeded: {e}") from e
            else:
                raise APIError(f"Gemini API request failed: {e}") from e

        # Extract usage (Gemini doesn't always return token info in simple response, assume estimate or use count_tokens)
        # Using count_tokens for input
        try:
           input_tokens = self.client.count_tokens(last_message).total_tokens # Rough estimate of last turn
           # For output, we count response text
           output_tokens = self.client.count_tokens(response.text).total_tokens
        except:
            input_tokens = len(last_message) // 4
            output_tokens = len(response.text) // 4
            
        cost = self.calculate_cost(input_tokens, output_tokens)

        # Update totals
        self.total_cost += cost
        self.total_tokens["input"] += input_tokens
        self.total_tokens["output"] += output_tokens

        content = response.text
        
        logger.debug(
            f"Gemini request complete: {input_tokens} in, {output_tokens} out, "
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
        # Clean model name (remove -exp, etc if needed for mapping)
        base_model = "gemini-1.5-flash"
        if "pro" in self.model:
            base_model = "gemini-1.5-pro"
        elif "2.0" in self.model:
            base_model = "gemini-2.0-flash"
            
        pricing = self.PRICING.get(base_model, self.PRICING["gemini-1.5-flash"])
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    async def filter_job(
        self,
        jd_markdown: str,
        resume_summary: str,
        preferences: str
    ):
        """Filter job using Gemini."""
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
        """Tailor resume using Gemini."""
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

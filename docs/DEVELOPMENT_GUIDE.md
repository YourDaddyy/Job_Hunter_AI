# Job Hunter AI - Development Guide

> **For Sub-Agents and Developers**
> **Last Updated:** 2026-01-30
> **Status:** Phase 3 Complete (100% Core Features)

This guide provides technical implementation details for developers and sub-agents working on the Job Hunter AI project.

---

## Agent Development Mode

This project uses Claude Code CLI as the orchestrator with specialized sub-agents for task implementation. When implementing new features:

1. **Read CLAUDE.md first** - Contains workflow and context
2. **Follow this guide** - Architecture and code standards
3. **Use Factory patterns** - For extensible components like LLM clients
4. **Test before marking complete** - Unit tests required

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [What's Implemented (Tasks 1-8)](#whats-implemented-tasks-1-8)
3. [Development Roadmap (Tasks 9+)](#development-roadmap-tasks-9)
4. [Architecture](#architecture)
5. [Development Setup](#development-setup)
6. [Code Standards](#code-standards)
7. [Key Components](#key-components)
8. [Database Schema](#database-schema)
9. [MCP Tools Reference](#mcp-tools-reference)
10. [Workflows](#workflows)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

---

## Project Overview

### Mission

Automate job hunting with AI assistance:
1. **Scrape** jobs from LinkedIn, Glassdoor, Wellfound, Indeed, and ATS platforms
2. **Filter** with AI (GLM) based on achievements and preferences
3. **Tailor** resumes automatically for high-match jobs
4. **Generate** daily campaign reports for user review
5. **Apply** with browser automation (user-controlled)

### Design Philosophy

- **Claude CLI as Manager:** Orchestrates workflow, not just a tool user
- **Hybrid Execution:** Automated (MCP) + Manual (Antigravity) tasks
- **Privacy First:** All data stored locally, minimal API calls
- **Cost Effective:** ~$0.20/day for 50 jobs processed
- **User Control:** Human approval before job applications

---

## What's Implemented (Tasks 1-8)

### ✅ Phase 1: Foundation (Tasks 1-2)

#### Task 1: Database Enhancement

**File:** `src/core/database.py`

**Changes:**
- Added `source` column (platform identifier)
- Added `source_priority` column (ATS=1, Visual=2, Other=3)
- Added `is_processed` column (GLM filtering status)
- Added `fuzzy_hash` column (company+title hash for cross-platform dedup)

**Note:** Schema is defined inline in `database.py`. No migration scripts needed - database is created fresh on first run.

**Schema:**
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    url TEXT NOT NULL,
    url_hash TEXT,                     -- MD5(url) for exact match
    fuzzy_hash TEXT,                   -- MD5(company+title) for fuzzy match
    source TEXT DEFAULT 'linkedin',    -- NEW: Platform source
    source_priority INTEGER DEFAULT 2, -- NEW: Priority level

    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    posted_date TEXT,

    ai_score REAL,                     -- GLM score (0-100)
    ai_reasoning TEXT,                 -- Why this score?
    is_processed BOOLEAN DEFAULT 0,    -- NEW: Has GLM filtered this?

    status TEXT DEFAULT 'pending',     -- pending|matched|rejected|applied
    decision_type TEXT,                -- auto|manual (for matched jobs)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_url_hash ON jobs(url_hash);
CREATE INDEX idx_jobs_fuzzy_hash ON jobs(fuzzy_hash);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_is_processed ON jobs(is_processed);
```

#### Task 2: Cleanup

**Removed Files (no longer in codebase):**
- Old Playwright scrapers (deprecated due to anti-bot measures)
- Old migration scripts (schema now inline in database.py)
- Test artifacts and temporary files

**Current Approach:** Use Antigravity visual browser agent for all job scraping tasks.

---

### ✅ Phase 2: Core Features (Tasks 3-5)

#### Task 3: Antigravity Instruction Generator

**Files Created:**
- `src/agents/instruction_generator.py` (457 lines)
- `src/agents/platform_configs.py` (platform-specific templates)
- `src/mcp_server/tools/antigravity.py` (MCP tool wrapper)

**Purpose:**
Generates JSON instruction files that guide Antigravity browser agent to scrape jobs.

**Input:**
- `config/preferences.md` (24 job titles, locations, filters)
- `config/credentials.md` (login credentials for auto-login)

**Output:**
- `instructions/scrape_jobs_{date}.json`

**Key Features:**
- Includes credentials for Antigravity auto-login
- Platform-specific natural language instructions
- Configurable search parameters
- Output file paths for each platform

**Example Output Structure:**
```json
{
  "_metadata": {
    "generated_at": "2026-01-29T10:30:00",
    "task_type": "scrape_jobs",
    "version": "1.0"
  },
  "credentials": {
    "linkedin": {"email": "...", "password": "..."},
    "glassdoor": {"email": "...", "password": "..."}
  },
  "search_parameters": {
    "job_titles": ["AI Engineer", "ML Engineer", ...],
    "locations": ["Remote", "Canada"],
    "filters": {
      "remote_only": true,
      "min_salary": 45000
    }
  },
  "platforms": [
    {
      "name": "linkedin",
      "priority": "high",
      "instructions": "1. Navigate to LinkedIn Jobs...",
      "output_file": "data/linkedin_2026-01-29.json"
    }
  ]
}
```

**MCP Tool:**
```python
@server.tool()
async def generate_antigravity_scraping_guide(
    date: str = None  # Optional, defaults to today
) -> dict:
    """
    Generates JSON instruction file for Antigravity.

    Returns:
        {
            "instruction_file": "instructions/scrape_jobs_2026-01-29.json",
            "platforms": ["linkedin", "glassdoor", "wellfound", "indeed"],
            "job_titles": 24,
            "message": "Please run: antigravity run {file}"
        }
    """
```

**Usage Workflow:**
1. Claude calls `generate_antigravity_scraping_guide()`
2. Tool generates `instructions/scrape_jobs_2026-01-29.json`
3. Claude tells user: "Please run: `antigravity run instructions/...`"
4. User runs Antigravity (manual task, ~5 minutes)
5. Antigravity scrapes and saves to `data/*.json`

#### Task 4: JSON Importer with Deduplication

**Files Created:**
- `src/core/importer.py` (457 lines)
- `src/mcp_server/tools/importer.py` (MCP tool wrapper)

**Purpose:**
Imports scraped JSON files from Antigravity to database with intelligent deduplication.

**Deduplication Strategy:**

**Two-Level System:**

1. **Level 1: URL Exact Match**
   ```python
   url_hash = hashlib.md5(url.encode()).hexdigest()
   # Check if url_hash exists in database
   ```

2. **Level 2: Fuzzy Hash**
   ```python
   def generate_fuzzy_hash(company: str, title: str) -> str:
       key = f"{company.lower().strip()}{title.lower().strip()}"
       return hashlib.md5(key.encode()).hexdigest()
   ```

**Source Priority Resolution:**

When fuzzy match found, compare `source_priority`:
- ATS platforms (Greenhouse, Lever, etc.) = priority 1 (highest)
- Visual platforms (LinkedIn, Indeed, etc.) = priority 2
- Other sources = priority 3

**Keep higher priority source** (lower number wins).

**Example:**
```
1. LinkedIn posts "Senior Engineer at Google" → Imported (priority=2)
2. Greenhouse posts "Senior Engineer at Google" → Replaces LinkedIn version (priority=1)
3. Indeed posts "Senior Engineer at Google" → Skipped (LinkedIn already has it, same priority)
```

**MCP Tool:**
```python
@server.tool()
async def import_antigravity_results(
    files: list = None  # Optional, defaults to data/*.json
) -> dict:
    """
    Imports scraped JSON files to database.

    Returns:
        {
            "total_jobs": 150,
            "new_jobs": 120,
            "url_duplicates": 15,
            "fuzzy_duplicates": 10,
            "updated_by_priority": 5,
            "imported_files": ["linkedin_2026-01-29.json", ...],
            "stats_by_source": {
                "linkedin": {"total": 80, "new": 65},
                "glassdoor": {"total": 40, "new": 30}
            }
        }
    """
```

**Input Format (from Antigravity):**
```json
[
  {
    "title": "AI Engineer",
    "company": "Scribd",
    "url": "https://jobs.lever.co/scribd/...",
    "description": "Full job description...",
    "salary": "$120k - $160k",
    "location": "Remote",
    "posted_date": "2 days ago",
    "easy_apply": true
  }
]
```

#### Task 5: GLM Processor with Three-Tier Scoring

**Files Created:**
- `src/core/gl_processor.py` (717 lines)
- `src/mcp_server/tools/gl_processor.py` (MCP tool wrapper)

**Purpose:**
Processes unfiltered jobs with GLM AI and routes to three tiers based on score.

**Three-Tier System:**

```
                    GLM Scoring (0-100)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
   Score ≥ 85          60 ≤ Score < 85      Score < 60
        │                   │                   │
        ▼                   ▼                   ▼
   TIER 1: HIGH        TIER 2: MEDIUM      TIER 3: LOW
   Auto-generate       Add to campaign     Auto-archive
   PDF resume          report (manual)     (rejected)
```

**Tier 1: HIGH MATCH (≥85)**
- Action: Auto-generate tailored PDF resume
- Status: `matched`
- Decision type: `auto`
- Resume saved to: `output/{Company}_{Role}.pdf`

**Tier 2: MEDIUM MATCH (60-84)**
- Action: Add to campaign report for user review
- Status: `matched`
- Decision type: `manual`
- User decides: approve (generate resume) or skip

**Tier 3: LOW MATCH (<60)**
- Action: Archive, no further processing
- Status: `rejected`
- Reasoning saved for reference

**GLM Filtering Process:**

1. **Load Context:**
   ```python
   achievements = load_markdown("config/achievements.md")
   preferences = load_markdown("config/preferences.md")
   ```

2. **For Each Unprocessed Job:**
   ```python
   prompt = f"""
   Score this job 0-100 based on:

   Job Description:
   {job.description}

   Candidate Achievements:
   {achievements}

   Preferences:
   {preferences}

   Return: {{"score": 0-100, "reasoning": "why this score"}}
   """

   response = await glm_client.chat(prompt)
   ```

3. **Route by Score:**
   ```python
   if score >= 85:  # Tier 1
       resume = await generate_tailored_resume(job)
       job.status = 'matched'
       job.decision_type = 'auto'
   elif score >= 60:  # Tier 2
       job.status = 'matched'
       job.decision_type = 'manual'
   else:  # Tier 3
       job.status = 'rejected'

   job.ai_score = score
   job.is_processed = True
   ```

**MCP Tool:**
```python
@server.tool()
async def process_jobs_with_glm_tool(
    force_reprocess: bool = False
) -> dict:
    """
    Process unfiltered jobs with GLM.

    Args:
        force_reprocess: Re-process jobs already filtered (default False)

    Returns:
        {
            "total_processed": 120,
            "tier1_high_match": 8,
            "tier2_medium_match": 18,
            "tier3_low_match": 94,
            "resumes_generated": 8,
            "cost_usd": 0.03,
            "failed": 0
        }
    """
```

**Resume Generation (Tier 1):**

Uses GLM API for cost-effective resume tailoring:
1. Read `config/resume.md` (base resume)
2. Read `config/achievements.md` (achievement pool)
3. Analyze job description and requirements
4. Select relevant achievements
5. Tailor resume content (summary, bullets, skills)
6. Generate PDF using `src/core/pdf_generator.py` + WeasyPrint

**Key Files:**
- `src/core/tailor.py` - ResumeTailoringService orchestration
- `src/core/llm/glm_client.py` - GLM API with `tailor_resume()` method
- `src/core/pdf_generator.py` - HTML to PDF with WeasyPrint

**Cost Tracking:**
- GLM filtering: ~$0.001 per job
- GLM resume tailoring: ~$0.003 per resume
- Example: 120 jobs + 8 resumes → ~$0.15 total

---

## Development Roadmap (Tasks 9+)

### 🔲 Task 9: Multi-LLM Provider Support

**Goal:** Enable users to choose different LLM providers for filtering and resume generation.

**Priority:** HIGH
**Complexity:** MEDIUM
**Estimated Files:** 6-8 new/modified files

#### Background

Currently the system uses:
- **GLM (智谱AI)** for both job filtering and resume tailoring
- Hardcoded provider in `gl_processor.py` and `tailor.py`

Users want flexibility to:
- Use different models for different tasks (e.g., GPT-4 for resume, GLM for filtering)
- Switch providers based on cost/quality tradeoffs
- Configure via simple markdown file

#### Supported Providers

| Provider | Models | Use Case | Pricing |
|----------|--------|----------|---------|
| GLM (智谱AI) | glm-4-flash | Filtering, Resume | $0.001/1K tokens |
| OpenAI | gpt-4o, gpt-4o-mini | High quality resume | $0.01-0.03/1K |
| Google Gemini | gemini-2.0-flash | Fast filtering | $0.001/1K tokens |
| Anthropic | claude-sonnet-4 | Best resume quality | $0.003-0.015/1K |
| MiniMax | abab6.5s | Chinese market | $0.002/1K tokens |
| OpenRouter | Any model | Unified gateway | Varies |

#### Architecture Design

```
config/llm_providers.md          # User configuration
        │
        ▼
src/core/llm/factory.py          # LLMFactory (creates clients)
        │
        ├── glm_client.py        # Existing
        ├── claude_client.py     # Existing
        ├── openai_client.py     # NEW
        ├── gemini_client.py     # NEW
        ├── minimax_client.py    # NEW
        └── openrouter_client.py # NEW (unified gateway)
        │
        ▼
src/core/gl_processor.py         # Uses factory for filter_client
src/core/tailor.py               # Uses factory for tailor_client
```

#### Sub-Task 9.1: Create Configuration File

**File:** `config/llm_providers.md`

```markdown
# LLM Provider Configuration

## Active Providers

### Filtering Provider
- Provider: glm
- Model: glm-4-flash
- Purpose: Job filtering (cost-effective)

### Resume Provider
- Provider: openai
- Model: gpt-4o-mini
- Purpose: Resume tailoring (high quality)

## Available Providers

### GLM (智谱AI)
- API Key Env: GLM_API_KEY
- Base URL: https://open.bigmodel.cn/api/paas/v4
- Models: glm-4-flash, glm-4-plus
- Notes: Best for Chinese + English content

### OpenAI
- API Key Env: OPENAI_API_KEY
- Models: gpt-4o, gpt-4o-mini, gpt-4-turbo
- Notes: Best overall quality

### Google Gemini
- API Key Env: GOOGLE_API_KEY
- Models: gemini-2.0-flash, gemini-1.5-pro
- Notes: Fast and cost-effective

### Anthropic Claude
- API Key Env: ANTHROPIC_API_KEY
- Models: claude-sonnet-4-20250514
- Notes: Excellent for writing tasks

### MiniMax
- API Key Env: MINIMAX_API_KEY
- Models: abab6.5s-chat
- Notes: Good for Chinese market

### OpenRouter (Unified Gateway)
- API Key Env: OPENROUTER_API_KEY
- Models: Any model via openrouter.ai
- Notes: Access 100+ models with single API key
```

**Acceptance Criteria:**
- [ ] Create `config/llm_providers.md` template
- [ ] Create parser in `src/utils/config.py`
- [ ] Add `LLMProviderConfig` dataclass
- [ ] Test parsing with different configurations

---

#### Sub-Task 9.2: Create LLM Factory

**File:** `src/core/llm/factory.py`

```python
"""LLM Factory for creating provider clients."""

from typing import Optional, Literal
from src.utils.config import ConfigLoader
from .base import BaseLLMClient
from .glm_client import GLMClient
from .claude_client import ClaudeClient

# Import new clients when implemented
# from .openai_client import OpenAIClient
# from .gemini_client import GeminiClient
# from .minimax_client import MiniMaxClient
# from .openrouter_client import OpenRouterClient

LLMPurpose = Literal["filter", "tailor"]


class LLMFactory:
    """Factory for creating LLM clients based on configuration."""

    _clients: dict[str, type[BaseLLMClient]] = {
        "glm": GLMClient,
        "claude": ClaudeClient,
        # "openai": OpenAIClient,
        # "gemini": GeminiClient,
        # "minimax": MiniMaxClient,
        # "openrouter": OpenRouterClient,
    }

    @classmethod
    def create_client(
        cls,
        purpose: LLMPurpose,
        config: Optional[ConfigLoader] = None
    ) -> BaseLLMClient:
        """Create LLM client for specified purpose.

        Args:
            purpose: "filter" or "tailor"
            config: Optional config loader (uses default if None)

        Returns:
            Configured LLM client instance

        Raises:
            ValueError: If provider not supported
        """
        config = config or ConfigLoader()
        provider_config = config.get_llm_provider(purpose)

        provider_name = provider_config.provider
        model = provider_config.model

        if provider_name not in cls._clients:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {list(cls._clients.keys())}"
            )

        client_class = cls._clients[provider_name]
        return client_class(model=model)

    @classmethod
    def register_client(
        cls,
        name: str,
        client_class: type[BaseLLMClient]
    ) -> None:
        """Register a new LLM client type."""
        cls._clients[name] = client_class

    @classmethod
    def list_providers(cls) -> list[str]:
        """List available provider names."""
        return list(cls._clients.keys())
```

**Acceptance Criteria:**
- [ ] Create `factory.py` with LLMFactory class
- [ ] Factory reads from `config/llm_providers.md`
- [ ] Support for "filter" and "tailor" purposes
- [ ] Client registration for extensibility
- [ ] Unit tests for factory creation

---

#### Sub-Task 9.3: Implement OpenAI Client

**File:** `src/core/llm/openai_client.py`

```python
"""OpenAI API client for job filtering and resume tailoring."""

import os
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseLLMClient, LLMResponse, TailoredResume, RateLimitError, APIError


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    PRICING = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini"
    ):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")

        super().__init__(api_key)
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """Send chat completion to OpenAI."""
        # Implementation similar to GLMClient
        pass

    async def filter_job(self, jd_markdown: str, resume_summary: str, preferences: str):
        """Filter job using OpenAI."""
        # Use same prompt format as GLMClient
        pass

    async def tailor_resume(self, resume_markdown: str, achievements_markdown: str, ...):
        """Tailor resume using OpenAI."""
        # Use same prompt format as GLMClient
        pass
```

**Acceptance Criteria:**
- [ ] Implement `openai_client.py`
- [ ] Async client with retry logic
- [ ] `chat()`, `filter_job()`, `tailor_resume()` methods
- [ ] Cost tracking per model
- [ ] Unit tests with mocked API

---

#### Sub-Task 9.4: Implement Gemini Client

**File:** `src/core/llm/gemini_client.py`

Similar structure to OpenAI client, using `google-generativeai` package.

**Acceptance Criteria:**
- [ ] Implement `gemini_client.py`
- [ ] Support gemini-2.0-flash and gemini-1.5-pro
- [ ] Async operations with retry
- [ ] Cost tracking

---

#### Sub-Task 9.5: Implement OpenRouter Client

**File:** `src/core/llm/openrouter_client.py`

OpenRouter provides unified access to 100+ models. This is the most flexible option.

```python
"""OpenRouter unified gateway client."""

class OpenRouterClient(BaseLLMClient):
    """OpenRouter API client - access any model."""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "anthropic/claude-sonnet-4"
    ):
        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        # OpenRouter uses OpenAI-compatible API
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL
        )
```

**Acceptance Criteria:**
- [ ] Implement `openrouter_client.py`
- [ ] Support any model via OpenRouter
- [ ] Dynamic pricing lookup
- [ ] Fallback to default model if unavailable

---

#### Sub-Task 9.6: Update Processor and Tailor

**Files to Modify:**
- `src/core/gl_processor.py`
- `src/core/tailor.py`

**Changes:**

```python
# gl_processor.py
from src.core.llm.factory import LLMFactory

class GLMProcessor:
    def __init__(self, llm_client=None):
        # Use factory instead of hardcoded GLMClient
        self.llm = llm_client or LLMFactory.create_client("filter")

# tailor.py
from src.core.llm.factory import LLMFactory

class ResumeTailoringService:
    def __init__(self, llm_client=None):
        # Use factory instead of hardcoded client
        self.llm = llm_client or LLMFactory.create_client("tailor")
```

**Acceptance Criteria:**
- [ ] Update `gl_processor.py` to use factory
- [ ] Update `tailor.py` to use factory
- [ ] Backward compatible (works without config file)
- [ ] Integration tests with different providers

---

#### Sub-Task 9.7: Update Package Exports

**File:** `src/core/llm/__init__.py`

```python
from .base import BaseLLMClient, LLMResponse, TailoredResume, ...
from .factory import LLMFactory
from .glm_client import GLMClient
from .claude_client import ClaudeClient
from .openai_client import OpenAIClient
from .gemini_client import GeminiClient
from .openrouter_client import OpenRouterClient

__all__ = [
    "BaseLLMClient",
    "LLMFactory",
    "GLMClient",
    "ClaudeClient",
    "OpenAIClient",
    "GeminiClient",
    "OpenRouterClient",
    ...
]
```

**Acceptance Criteria:**
- [ ] Update `__init__.py` with new exports
- [ ] Ensure backward compatibility
- [ ] Add docstrings for module

---

### ✅ Task 10: Advanced Features (Complete)

All advanced features have been implemented:

#### Task 10.1: ATS Dorking Scanner ✅
- **Files:** `src/scrapers/ats_scanner.py`, `src/mcp_server/tools/ats_scanner.py`
- Google dorking for Greenhouse, Lever, Ashby, Workable
- DuckDuckGo search backend (avoids Google anti-bot)
- Platform-specific CSS selectors for job extraction
- Automatic database import with deduplication

#### Task 10.2: Campaign Report Generator ✅
- **Files:** `src/output/report_generator.py`, `src/mcp_server/tools/report.py`
- Daily Markdown reports with HIGH/MEDIUM match tables
- Statistics and cost breakdown
- Next steps guidance for user

#### Task 10.3: Application Instruction Generator ✅
- **Files:** `src/agents/application_guide_generator.py`, `src/mcp_server/tools/application.py`
- JSON instructions for Antigravity auto-apply
- Platform-specific form filling instructions
- Safety controls (pause before submit, rate limiting)

---

## Architecture

See `docs/ARCHITECTURE.md` for detailed architecture diagrams and design decisions.

**Key Points:**
- Hybrid MCP (automated) + Antigravity (manual) execution
- SQLite with source tracking and fuzzy deduplication
- Three-tier scoring (85/60 thresholds)
- Privacy-first (local data only)

---

## Development Setup

### 1. Environment Setup

```bash
# Clone repository
cd .

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with API keys
# - GLM_API_KEY (智谱AI)
# - ANTHROPIC_API_KEY (optional, for resume tailoring)

# Copy config templates
cp config/resume.example.md config/resume.md
cp config/preferences.example.md config/preferences.md
cp config/achievements.example.md config/achievements.md
cp config/credentials.example.md config/credentials.md

# Edit config files with your information
```

### 3. Initialize Database

```bash
python -m src.core.database init
```

### 4. Test MCP Server

```bash
# Start MCP server
python -m src.mcp_server.server

# In another terminal, test tools
python -c "from src.mcp_server.tools.antigravity import generate_antigravity_scraping_guide; print(generate_antigravity_scraping_guide())"
```

---

## Code Standards

### Python Style

- **Version:** Python 3.10+
- **Style Guide:** PEP 8
- **Line Length:** 100 characters max
- **Type Hints:** Always use for function signatures
- **Docstrings:** Google style

```python
def process_jobs_with_glm(
    batch_size: int = 50,
    force_reprocess: bool = False
) -> dict[str, any]:
    """Process unfiltered jobs with GLM AI.

    Args:
        batch_size: Number of jobs to process in each batch
        force_reprocess: Re-process already filtered jobs

    Returns:
        Dictionary containing:
            - total_processed: Number of jobs processed
            - tier1_high_match: Count of high match jobs (≥85)
            - tier2_medium_match: Count of medium match jobs (60-84)
            - tier3_low_match: Count of low match jobs (<60)
            - resumes_generated: Number of resumes auto-generated
            - cost_usd: Total API cost

    Raises:
        APIError: If GLM API call fails
        DatabaseError: If database update fails
    """
    pass
```

### Error Handling

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def scrape_platform(platform: str):
    try:
        # Main logic
        result = await do_scraping()
    except ConnectionError as e:
        logger.error(f"Network error for {platform}: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in {platform}")
        raise
```

### Import Order

```python
# Standard library
import os
import json
from typing import Optional, List

# Third party
from playwright.async_api import async_playwright
from mcp import Server

# Local
from src.core.database import Database
from src.utils.logger import get_logger
```

---

## Key Components

### Database (src/core/database.py)

```python
from src.core.database import Database

db = Database()

# Insert job with deduplication
job_data = {
    "external_id": "12345",
    "url": "https://...",
    "title": "AI Engineer",
    "company": "Scribd",
    "source": "linkedin",
    "source_priority": 2
}

job_id = db.insert_job(job_data)

# Get unprocessed jobs
unprocessed = db.get_unprocessed_jobs(limit=50)

# Update job after GLM processing
db.update_job_score(
    job_id=123,
    ai_score=85,
    ai_reasoning="Strong match...",
    status="matched",
    decision_type="auto",
    is_processed=True
)
```

### Importer (src/core/importer.py)

```python
from src.core.importer import AntigravityImporter

importer = AntigravityImporter()

# Import single file
result = importer.import_file("data/linkedin_2026-01-29.json")
# Returns: {"total": 80, "new": 65, "url_dups": 10, "fuzzy_dups": 5}

# Import all files in data/
result = importer.import_multiple_files()
# Returns: {"total_jobs": 150, "new_jobs": 120, ...}
```

### GLM Processor (src/core/gl_processor.py)

```python
from src.core.gl_processor import GLMProcessor

processor = GLMProcessor()

# Process all unfiltered jobs
result = await processor.process_all_unfiltered()
# Returns: {
#     "total_processed": 120,
#     "tier1_high_match": 8,
#     "tier2_medium_match": 18,
#     "tier3_low_match": 94,
#     "resumes_generated": 8,
#     "cost_usd": 0.19
# }
```

---

## Database Schema

See full schema in `docs/ARCHITECTURE.md#database-schema`.

**Key Tables:**

```sql
-- Jobs table (updated)
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    url TEXT NOT NULL,
    url_hash TEXT,
    fuzzy_hash TEXT,
    source TEXT DEFAULT 'linkedin',
    source_priority INTEGER DEFAULT 2,

    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    posted_date TEXT,

    ai_score REAL,
    ai_reasoning TEXT,
    is_processed BOOLEAN DEFAULT 0,

    status TEXT DEFAULT 'pending',
    decision_type TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_jobs_url_hash ON jobs(url_hash);
CREATE INDEX idx_jobs_fuzzy_hash ON jobs(fuzzy_hash);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_is_processed ON jobs(is_processed);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_ai_score ON jobs(ai_score);
```

---

## MCP Tools Reference

### Implemented Tools

| Tool | File | Purpose |
|------|------|---------|
| `generate_antigravity_scraping_guide` | `tools/antigravity.py` | Generate JSON for Antigravity scraping |
| `import_antigravity_results` | `tools/importer.py` | Import scraped JSON to database |
| `process_jobs_with_glm_tool` | `tools/gl_processor.py` | Filter jobs with GLM, three-tier routing |
| `tailor_resume` | `tools/tailor.py` | Generate tailored PDF resume for job |

### Advanced Tools (Task 10) ✅

| Tool | File | Purpose |
|------|------|---------|
| `scan_ats_platforms_tool` | `tools/ats_scanner.py` | Google dork ATS platforms |
| `generate_campaign_report_tool` | `tools/report.py` | Generate daily campaign report |
| `generate_application_instructions_tool` | `tools/application.py` | Generate Antigravity apply instructions |

---

## Workflows

### Daily Job Hunt Workflow (Current)

```
1. User: "Start job hunt"

2. Claude → generate_antigravity_scraping_guide()
   → Creates instructions/scrape_jobs_2026-01-29.json

3. Claude: "Please run: antigravity run instructions/..."

4. User: [Runs Antigravity, ~5 min]
   → Saves to data/*.json

5. User: "Done scraping"

6. Claude → import_antigravity_results()
   → Imports 150 jobs, deduplicates to 120 unique

7. Claude → process_jobs_with_glm_tool()
   → Scores all 120 jobs
   → Generates 8 resumes for Tier 1 (≥85)
   → Marks 18 as Tier 2 (60-84) for user review

8. Claude: "Processing complete. 8 high matches with resumes ready, 18 medium matches for review."
```

### Daily Workflow (After Task 6-8)

```
1-5. [Same as above]

6. Claude → import_antigravity_results()

7. Claude → scan_ats_platforms()  [NEW - Task 6]
   → Finds 45 ATS jobs, imports 30 new

8. Claude → process_jobs_with_glm_tool()
   → Scores all jobs (120 + 30 = 150)

9. Claude → generate_campaign_report()  [NEW - Task 7]
   → Creates campaigns/campaign_2026-01-29.md

10. Claude: "Report ready at campaigns/campaign_2026-01-29.md"

11. User: Reviews report, approves some medium matches

12. Claude → generate_application_instructions()  [NEW - Task 8]
    → Creates instructions/apply_jobs_2026-01-29.json

13. Claude: "Please run: antigravity run instructions/apply_jobs_..."

14. User: [Runs Antigravity to auto-apply, ~5 min]
    → Antigravity pauses before each submit

15. User: Reviews each application, clicks Submit
```

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_importer.py

# Run with coverage
pytest --cov=src --cov-report=html
```

### Integration Tests

```bash
# Mark tests as integration
@pytest.mark.integration
async def test_full_workflow():
    ...

# Run only integration tests
pytest -m integration
```

### Manual Testing

```bash
# Test instruction generator
python -m src.agents.instruction_generator

# Test importer
python -m src.core.importer data/linkedin_test.json

# Test GLM processor (with limit)
python -m src.core.gl_processor --limit 5
```

---

## Troubleshooting

### Common Issues

**1. "GLM API error: rate limit"**
- Solution: Wait 60 seconds, reduce batch size
- Check: API key quota at https://open.bigmodel.cn/

**2. "Database locked"**
- Solution: Ensure WAL mode enabled
- Fix: `PRAGMA journal_mode=WAL`

**3. "Fuzzy duplicates not working"**
- Check: Both jobs have company and title
- Debug: Print fuzzy_hash for both jobs

**4. "Resume generation failed"**
- Check: `config/resume.md` exists
- Check: `config/achievements.md` exists
- Check: GLM API key in .env (GLM_API_KEY)
- Check: WeasyPrint and GTK3 installed for PDF generation

**5. "Antigravity login failed"**
- Update: `config/credentials.md`
- Try: Manual login first to clear CAPTCHAs
- Check: Account not locked

### Debug Logging

```python
# Enable debug logging
import logging
logging.getLogger("src").setLevel(logging.DEBUG)
```

### Database Debugging

```bash
# Open SQLite
sqlite3 data/jobs.db

# Check tables
.tables
.schema jobs

# Query jobs
SELECT id, company, title, ai_score, status FROM jobs WHERE status='matched';
SELECT COUNT(*), status FROM jobs GROUP BY status;
```

---

## Development Status

### All Tasks Complete ✅

| Task | Description | Status |
|------|-------------|--------|
| Task 1-5 | Foundation & Core Features | ✅ Complete |
| Task 6-8 | Antigravity Integration | ✅ Complete |
| Task 9 | Multi-LLM Provider Support | ✅ Complete |
| Task 10 | ATS Scanner, Reports, Applications | ✅ Complete |

### Implemented LLM Providers

| Provider | Client File | Status |
|----------|-------------|--------|
| GLM (智谱AI) | `glm_client.py` | ✅ Default |
| OpenAI | `openai_client.py` | ✅ Available |
| Google Gemini | `gemini_client.py` | ✅ Available |
| Anthropic Claude | `claude_client.py` | ✅ Available |
| OpenRouter | `openrouter_client.py` | ✅ Available |

### Configuration

To switch LLM providers, edit `config/llm_providers.md`:

```markdown
### Filtering Provider
- Provider: openai    # Change from 'glm'
- Model: gpt-4o-mini

### Resume Provider
- Provider: claude
- Model: claude-sonnet-4-20250514
```

### Development Best Practices

1. **Read CLAUDE.md** for project context and workflow
2. **Read this guide** before starting implementation
3. **Follow code standards** (PEP 8, type hints, docstrings)
4. **Use existing patterns** from `glm_client.py` and `claude_client.py`
5. **Write unit tests** for new components
6. **Test manually** before marking complete

---

## References

- **CLAUDE.md** - Agent guide and workflow reference
- **README.md** - User guide and quick start
- **docs/ARCHITECTURE.md** - Architecture and design decisions
- **config/*.example.md** - Configuration templates

---

**Last Updated:** 2026-01-30
**Project Status:** ALL TASKS COMPLETE (100%)
**Available Features:** Multi-LLM, ATS Scanner, Reports, Auto-Apply

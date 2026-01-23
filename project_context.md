# Project Specification: AI-Powered Autonomous Job Search & Application System

## 1. Project Vision

To solve the time-constraint pain point in the job hunting process by developing a 24/7 autonomous agent system. The system acts as a "Digital Headhunter" that searches for, filters, and applies to high-quality AI/Backend remote roles in the US and Canada while the user is away from their computer.

**Core Principle:** Claude Code CLI as the main orchestrator, using MCP Server to provide job hunting tools.

---

## 2. System Architecture

The project follows a **MCP Server + Claude Code CLI** pattern for orchestration.

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Claude Code CLI (Main Orchestrator)              │
│                                                                          │
│   User: "开始今天的求职任务"                                              │
│   Claude: 调用 MCP Tools 完成抓取→筛选→决策→投递→通知                    │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    job-hunter MCP Server                         │   │
│   │                                                                  │   │
│   │   Tools:                              Resources:                 │   │
│   │   • scrape_jobs()                     • resume://current        │   │
│   │   • filter_jobs_with_glm()            • preferences://config    │   │
│   │   • get_matched_jobs()                • achievements://list     │   │
│   │   • check_duplicate()                 • jobs://pending          │   │
│   │   • decide_and_apply()                                          │   │
│   │   • tailor_resume()                                             │   │
│   │   • apply_to_job()                                              │   │
│   │   • send_telegram_notification()                                │   │
│   │   • ask_user_decision()                                         │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                         Core Services                            │   │
│   │                                                                  │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │   │
│   │  │ Scraper  │  │  Filter  │  │ Tailor   │  │   Applier    │    │   │
│   │  │Playwright│  │   GLM    │  │ Claude   │  │  Playwright  │    │   │
│   │  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │   │
│   │                                                                  │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────────────────────────┐  │   │
│   │  │ Database │  │ Telegram │  │      Deduplication           │  │   │
│   │  │  SQLite  │  │   Bot    │  │  (external_id + url hash)    │  │   │
│   │  └──────────┘  └──────────┘  └──────────────────────────────┘  │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Data Files (Markdown):
📄 config/resume.md          - 简历信息
📄 config/preferences.md     - 求职偏好
📄 config/achievements.md    - 项目经历/成就
```

### 2.2 Component Responsibilities

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| **Claude Code CLI** | Claude API | Main orchestrator, high-level decision making, natural language interface |
| **MCP Server** | Python + MCP SDK | Provides tools for job hunting workflow |
| **Scraper** | Playwright | Extracts job data from LinkedIn, Indeed, Wellfound |
| **Filter** | GLM API (cheap) | High-throughput JD screening, match scoring |
| **Tailor** | Claude API | Resume customization based on JD |
| **Applier** | Playwright | Automated form filling and submission |
| **Deduplicator** | SQLite | Prevents duplicate applications |
| **Telegram Bot** | python-telegram-bot | Notifications and user decisions |

### 2.3 Intelligent Decision Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Intelligent Decision Flow                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Scrape Jobs                                                            │
│       │                                                                  │
│       ▼                                                                  │
│   ┌─────────────┐                                                        │
│   │ Deduplicate │──── Already applied? ──── Yes ───→ Skip               │
│   └─────────────┘                                                        │
│       │ No                                                               │
│       ▼                                                                  │
│   ┌─────────────┐                                                        │
│   │ GLM Filter  │──── Score < 0.60 ──── Reject (低匹配)                  │
│   │  (便宜)     │                                                        │
│   └─────────────┘                                                        │
│       │ Score >= 0.60                                                    │
│       ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     Decision Logic                               │   │
│   │                                                                  │   │
│   │   Score >= 0.85 (高匹配)                                         │   │
│   │       │                                                          │   │
│   │       ▼                                                          │   │
│   │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │   │
│   │   │Tailor Resume│ →  │Auto Apply   │ →  │  Telegram   │         │   │
│   │   │  (Claude)   │    │(Playwright) │    │  通知结果    │         │   │
│   │   └─────────────┘    └─────────────┘    └─────────────┘         │   │
│   │                                                                  │   │
│   │   Score 0.60-0.85 (中匹配)                                       │   │
│   │       │                                                          │   │
│   │       ▼                                                          │   │
│   │   ┌─────────────┐    ┌─────────────┐                            │   │
│   │   │ 加入待决策   │ →  │等待本轮完成 │                            │   │
│   │   │   队列      │    │             │                            │   │
│   │   └─────────────┘    └──────┬──────┘                            │   │
│   │                              │                                   │   │
│   │                              ▼                                   │   │
│   │                     ┌─────────────┐                             │   │
│   │                     │  Telegram   │                             │   │
│   │                     │  询问用户    │                             │   │
│   │                     └──────┬──────┘                             │   │
│   │                            │                                     │   │
│   │              ┌─────────────┴─────────────┐                      │   │
│   │              ▼                           ▼                      │   │
│   │        User: Approve              User: Skip                    │   │
│   │              │                           │                      │   │
│   │              ▼                           ▼                      │   │
│   │        Tailor & Apply              Mark Skipped                 │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Decision Thresholds (configurable):
• auto_apply_threshold: 0.85  (>=85% 自动投递)
• notify_threshold: 0.60      (>=60% 通知用户决策)
• reject below 0.60           (<60% 自动拒绝)
```

---

## 3. Core Technical Modules

### A. Job Scraping (Playwright)

**Supported Platforms:**
- LinkedIn (Easy Apply)
- Indeed
- Wellfound (AngelList)

**Features:**
- Headed mode for anti-detection
- Smart delays (2-8 seconds random)
- Session persistence via browser profile
- Structured data extraction (title, company, JD, salary, location)

### B. Deduplication System

**Multi-layer Deduplication:**

```python
# Layer 1: External ID (platform-specific job ID)
# LinkedIn: job ID from URL
# Indeed: job key
# Wellfound: job slug

# Layer 2: URL Hash (fallback)
url_hash = hashlib.md5(job_url.encode()).hexdigest()

# Layer 3: Content Similarity (optional)
# For jobs reposted with different IDs
similarity = compare_jd_content(new_jd, existing_jds)
if similarity > 0.95:
    mark_as_duplicate()
```

**Database Support:**
```sql
-- Unique constraints for deduplication
CREATE UNIQUE INDEX idx_jobs_external_id ON jobs(platform, external_id);
CREATE UNIQUE INDEX idx_jobs_url_hash ON jobs(url_hash);

-- Application history for duplicate prevention
CREATE TABLE applications (
    job_id INTEGER REFERENCES jobs(id),
    status TEXT,  -- 'applied', 'skipped', 'failed'
    UNIQUE(job_id)
);
```

### C. LLM Integration (Cost-Optimized)

**GLM (便宜 - 用于筛选):**
- Batch filtering of job descriptions
- Match scoring (0-1)
- Key requirements extraction
- Red flags detection
- Estimated cost: ~$0.5-2/day for 500 JDs

**Claude (高质量 - 用于决策和简历):**
- Final application decisions
- Resume tailoring
- Cover letter generation
- Estimated cost: ~$0.5-1/day for 20 applications

### D. Resume Tailoring

**Process:**
1. Load base resume from `config/resume.md`
2. Load achievements from `config/achievements.md`
3. Claude analyzes JD requirements
4. Select relevant achievements/skills to highlight
5. Generate tailored resume
6. Convert to PDF via WeasyPrint

**No RAG/Vector DB needed** - Claude directly reads markdown files and makes intelligent selections.

### E. Telegram Integration

**Notification Types:**
- High-match auto-apply results
- Medium-match jobs awaiting decision
- Daily summary digest
- Error alerts (CAPTCHA, login issues)

**Interactive Commands:**
| Command | Action |
|---------|--------|
| `/status` | Show today's pipeline stats |
| `/pending` | List jobs awaiting decision |
| `/approve <id>` | Approve job for application |
| `/skip <id>` | Skip job |
| `/pause` | Pause automation |
| `/resume` | Resume automation |
| `/daily` | Send daily digest |

---

## 4. Database Schema

```sql
-- Core job data
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification (for deduplication)
    external_id TEXT,                      -- Platform-specific job ID
    url_hash TEXT,                         -- MD5 hash of job URL
    platform TEXT NOT NULL,                -- 'linkedin', 'indeed', 'wellfound'
    url TEXT NOT NULL,

    -- Job details
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency TEXT DEFAULT 'USD',
    remote_type TEXT,                      -- 'remote', 'hybrid', 'onsite'
    visa_sponsorship BOOLEAN,

    -- Content
    jd_markdown TEXT,                      -- Cleaned job description
    jd_raw TEXT,                           -- Original HTML

    -- Filtering results
    match_score REAL,                      -- 0.0 to 1.0
    match_reasoning TEXT,                  -- LLM explanation
    key_requirements TEXT,                 -- JSON array
    red_flags TEXT,                        -- JSON array

    -- Status tracking
    status TEXT DEFAULT 'new',             -- 'new', 'filtered', 'matched', 'pending_decision', 'approved', 'rejected', 'applied', 'skipped', 'failed'
    decision_type TEXT,                    -- 'auto', 'manual'

    -- Timestamps
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filtered_at TIMESTAMP,
    decided_at TIMESTAMP,
    applied_at TIMESTAMP,

    -- Constraints
    UNIQUE(platform, external_id),
    UNIQUE(url_hash)
);

-- Application tracking
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER UNIQUE REFERENCES jobs(id),
    resume_path TEXT,
    cover_letter_path TEXT,
    status TEXT DEFAULT 'pending',         -- 'pending', 'submitted', 'failed'
    error_message TEXT,
    attempts INTEGER DEFAULT 0,
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generated resumes
CREATE TABLE resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    pdf_path TEXT NOT NULL,
    highlights TEXT,                       -- JSON: achievements used
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Run history (for tracking each automation run)
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    jobs_scraped INTEGER DEFAULT 0,
    jobs_filtered INTEGER DEFAULT 0,
    jobs_matched INTEGER DEFAULT 0,
    jobs_auto_applied INTEGER DEFAULT 0,
    jobs_pending_decision INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'          -- 'running', 'completed', 'failed'
);

-- Blacklist
CREATE TABLE blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,                    -- 'company', 'keyword', 'job_id', 'url'
    value TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(type, value)
);

-- Audit logs
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,                            -- 'debug', 'info', 'warn', 'error'
    component TEXT,                        -- 'scraper', 'filter', 'applier', etc.
    message TEXT,
    details TEXT,                          -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_match_score ON jobs(match_score);
CREATE INDEX idx_jobs_scraped_at ON jobs(scraped_at);
CREATE INDEX idx_applications_job_id ON applications(job_id);
```

---

## 5. Configuration Files (Markdown)

### 5.1 Resume (`config/resume.md`)

```markdown
# Personal Information

- Name: [Your Name]
- Email: your.email@example.com
- Phone: +1-xxx-xxx-xxxx
- LinkedIn: linkedin.com/in/yourprofile
- GitHub: github.com/yourusername
- Location: Vancouver, Canada
- Visa Status: Requires sponsorship

# Summary

Senior Software Engineer with 5+ years of experience in AI/ML systems and backend development.
Specialized in building scalable distributed systems and implementing RAG pipelines.

# Education

## [University Name]
- Degree: Master of Computer Science
- Period: 2018 - 2020
- GPA: 3.8/4.0
- Relevant Coursework: Machine Learning, Distributed Systems, NLP

# Work Experience

## Senior Software Engineer @ Company A
- Period: 2022.06 - Present
- Location: Remote

### Responsibilities
- Led development of enterprise AI platform serving 10K+ users
- Implemented RAG pipeline reducing response latency by 40%
- Managed team of 4 engineers

### Technologies
Python, PyTorch, FastAPI, PostgreSQL, Redis, AWS

## Software Engineer @ Company B
- Period: 2019.01 - 2022.05
- Location: Vancouver, Canada

### Responsibilities
- Built high-throughput messaging system processing 1M+ events/day
- Designed Kafka-based event streaming architecture
- Achieved 99.9% uptime for critical services

### Technologies
Java, Kafka, Kubernetes, Spring Boot, MySQL

# Skills

## Programming Languages
Python, Java, TypeScript, Go, SQL

## AI/ML
PyTorch, TensorFlow, LangChain, RAG, LLM Fine-tuning, Prompt Engineering

## Backend
FastAPI, Spring Boot, Node.js, PostgreSQL, Redis, Kafka, RabbitMQ

## DevOps & Cloud
Docker, Kubernetes, AWS (EC2, S3, Lambda), GCP, Terraform

## Tools
Git, Linux, CI/CD, Monitoring (Prometheus, Grafana)
```

### 5.2 Preferences (`config/preferences.md`)

```markdown
# Job Search Preferences

## Target Positions
- AI Engineer
- ML Engineer
- Machine Learning Engineer
- Backend Engineer
- Software Engineer
- Python Developer
- Senior Software Engineer

## Location Requirements

### Preferred
- Remote (fully remote)
- United States (remote)
- Canada (remote)

### Acceptable
- Hybrid (max 2 days/week in office)
- US/Canada timezone-aligned remote

### Not Acceptable
- Onsite only
- Relocation required
- Non-US/Canada timezones

## Work Authorization
- Current Status: Work Permit (Canada)
- Requires Visa Sponsorship: Yes
- Willing to Relocate: Only for exceptional opportunities

## Salary Expectations
- Minimum: $120,000 USD/year
- Target: $150,000 - $200,000 USD/year
- Currency: USD preferred, CAD acceptable
- Note: Open to discussion for exceptional roles

## Company Preferences

### Blacklist (Do not apply)
- Revature
- Infosys
- Wipro
- TCS
- Cognizant
- Any staffing/consulting agency

### Preferred Company Types
- Product companies
- AI-focused startups (Series A+)
- Tech giants with AI teams
- Research labs

## Keyword Filters

### Must NOT contain (auto-reject)
- "clearance required"
- "security clearance"
- "US citizen only"
- "no sponsorship"
- "must be authorized to work without sponsorship"
- "contract to hire" (staffing)
- "W2 only through our vendor"

### Preferred keywords (bonus points)
- "visa sponsorship available"
- "we sponsor visas"
- "remote friendly"
- "distributed team"
- "AI/ML team"
- "LLM"
- "RAG"

## Application Settings

### Decision Thresholds
- auto_apply_threshold: 0.85    # Score >= 85% → auto apply
- notify_threshold: 0.60        # Score 60-85% → ask user
- reject_threshold: 0.60        # Score < 60% → auto reject

### Rate Limits
- max_applications_per_day: 20
- max_applications_per_hour: 5
- scrape_interval_hours: 4      # How often to check for new jobs

### Platforms
- linkedin: enabled
- indeed: enabled
- wellfound: enabled
```

### 5.3 Achievements (`config/achievements.md`)

```markdown
# Career Achievements

Use these achievements to tailor resume based on job requirements.

## AI/ML Projects

### Newland AI Platform
- Category: AI, Backend, Leadership
- Keywords: AI, RAG, LLM, Python, FastAPI, Vector Database
- Bullets:
  - Led development of enterprise AI platform serving 10K+ daily active users
  - Implemented RAG pipeline with ChromaDB, reducing response latency by 40%
  - Designed multi-tenant architecture supporting 50+ enterprise clients
  - Integrated multiple LLM providers (OpenAI, Anthropic) with fallback mechanisms

### Vibe Coding Assistant
- Category: AI, Developer Tools
- Keywords: LLM, Code Generation, Python, VS Code Extension
- Bullets:
  - Built AI-powered coding assistant with context-aware code completion
  - Achieved 85% acceptance rate for AI-generated suggestions
  - Implemented streaming responses for real-time code generation

## Backend Projects

### Global Relay LING Messaging System
- Category: Backend, Messaging, High-Scale
- Keywords: Kafka, Java, Microservices, Event-Driven, High-Throughput
- Bullets:
  - Architected high-throughput messaging system processing 1M+ events/day
  - Implemented Kafka-based event streaming with exactly-once semantics
  - Achieved 99.9% uptime through redundancy and graceful degradation
  - Reduced message processing latency by 60% through optimization

### Payment Processing Service
- Category: Backend, FinTech
- Keywords: Payment, Security, Compliance, PostgreSQL, Redis
- Bullets:
  - Designed PCI-DSS compliant payment processing service
  - Implemented idempotent transaction handling preventing duplicate charges
  - Built real-time fraud detection system reducing chargebacks by 35%

## Full-Stack Projects

### Analytics Dashboard
- Category: Full-Stack, Data Visualization
- Keywords: React, TypeScript, D3.js, FastAPI, PostgreSQL
- Bullets:
  - Built real-time analytics dashboard with sub-second query performance
  - Implemented complex data visualizations using D3.js
  - Designed efficient data aggregation pipeline handling 10TB+ data

## Leadership & Soft Skills

### Team Leadership
- Category: Leadership
- Keywords: Team Lead, Mentorship, Agile
- Bullets:
  - Led team of 4-6 engineers across multiple time zones
  - Implemented agile practices improving sprint velocity by 30%
  - Mentored 3 junior engineers, all promoted within 18 months

### Technical Writing
- Category: Communication
- Keywords: Documentation, Technical Writing
- Bullets:
  - Authored technical documentation reducing onboarding time by 50%
  - Published 5 engineering blog posts with 10K+ total views
```

---

## 6. MCP Server Implementation

### 6.1 Server Structure

```
src/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py              # MCP Server entry point
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── scraper.py         # scrape_jobs tool
│   │   ├── filter.py          # filter_jobs_with_glm tool
│   │   ├── deduplicator.py    # check_duplicate tool
│   │   ├── decision.py        # decide_and_apply tool
│   │   ├── tailor.py          # tailor_resume tool
│   │   ├── applier.py         # apply_to_job tool
│   │   └── notifier.py        # telegram tools
│   └── resources/
│       ├── __init__.py
│       ├── resume.py          # resume:// resource
│       ├── preferences.py     # preferences:// resource
│       └── jobs.py            # jobs:// resource
│
├── core/
│   ├── __init__.py
│   ├── database.py            # SQLite operations
│   ├── browser.py             # Playwright wrapper
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── glm_client.py      # GLM API client
│   │   └── claude_client.py   # Claude API client
│   ├── pdf_generator.py       # WeasyPrint wrapper
│   └── telegram.py            # Telegram bot
│
└── utils/
    ├── __init__.py
    ├── config.py              # Configuration loader
    ├── markdown_parser.py     # Parse config markdown files
    └── logging.py             # Logging setup
```

### 6.2 MCP Tools Definition

```python
# src/mcp_server/server.py

from mcp.server import Server
import mcp.server.stdio

server = Server("job-hunter")

@server.tool()
async def scrape_jobs(
    platform: str = "all",
    limit: int = 100
) -> dict:
    """
    从招聘网站抓取最新职位

    Args:
        platform: 平台选择 (linkedin/indeed/wellfound/all)
        limit: 每个平台最大抓取数量

    Returns:
        {
            "status": "success",
            "total_scraped": 150,
            "new_jobs": 120,      # 去重后的新职位
            "duplicates": 30,     # 已存在的重复职位
            "by_platform": {...}
        }
    """
    pass

@server.tool()
async def filter_jobs_with_glm(
    batch_size: int = 50
) -> dict:
    """
    使用 GLM 模型筛选新抓取的职位 (成本低)

    Args:
        batch_size: 每批处理数量

    Returns:
        {
            "status": "success",
            "total_processed": 120,
            "high_match": 8,      # >= 0.85
            "medium_match": 15,   # 0.60 - 0.85
            "rejected": 97       # < 0.60
        }
    """
    pass

@server.tool()
async def get_matched_jobs(
    min_score: float = 0.60,
    status: str = "matched",
    limit: int = 20
) -> list:
    """
    获取符合条件的职位列表

    Returns:
        职位列表，按匹配分数排序
    """
    pass

@server.tool()
async def check_duplicate(
    job_url: str = None,
    external_id: str = None,
    platform: str = None
) -> dict:
    """
    检查职位是否已存在或已投递

    Returns:
        {
            "is_duplicate": true/false,
            "reason": "already_applied" / "already_scraped" / "blacklisted" / null,
            "existing_job_id": 123 or null
        }
    """
    pass

@server.tool()
async def process_high_match_jobs() -> dict:
    """
    自动处理高匹配职位 (score >= 0.85)

    流程: 获取高匹配职位 → 生成简历 → 自动投递 → 记录结果

    Returns:
        {
            "status": "success",
            "processed": 5,
            "applied": 4,
            "failed": 1,
            "details": [...]
        }
    """
    pass

@server.tool()
async def get_pending_decisions() -> list:
    """
    获取等待用户决策的中匹配职位 (0.60 <= score < 0.85)

    Returns:
        待决策职位列表
    """
    pass

@server.tool()
async def tailor_resume(job_id: int) -> dict:
    """
    根据职位要求定制简历

    Args:
        job_id: 职位ID

    Returns:
        {
            "status": "success",
            "pdf_path": "data/resumes/123.pdf",
            "highlights": ["achievement1", "achievement2"],
            "tailoring_notes": "Emphasized RAG experience..."
        }
    """
    pass

@server.tool()
async def apply_to_job(
    job_id: int,
    resume_path: str = None
) -> dict:
    """
    自动投递职位

    Args:
        job_id: 职位ID
        resume_path: 简历路径 (可选，不提供则使用已生成的)

    Returns:
        {
            "status": "success" / "failed",
            "job_id": 123,
            "company": "Anthropic",
            "title": "AI Engineer",
            "error": null or "error message"
        }
    """
    pass

@server.tool()
async def approve_job(job_id: int) -> dict:
    """
    用户批准中匹配职位，触发投递流程
    """
    pass

@server.tool()
async def skip_job(job_id: int, reason: str = None) -> dict:
    """
    用户跳过职位
    """
    pass

@server.tool()
async def send_telegram_notification(
    message: str,
    parse_mode: str = "Markdown"
) -> dict:
    """
    发送 Telegram 通知
    """
    pass

@server.tool()
async def send_pending_decisions_to_telegram() -> dict:
    """
    将待决策职位发送到 Telegram 等待用户回复

    Returns:
        {
            "status": "success",
            "jobs_sent": 5,
            "message_ids": [...]
        }
    """
    pass

@server.tool()
async def get_run_summary() -> dict:
    """
    获取当前运行的统计摘要

    Returns:
        {
            "run_id": 1,
            "started_at": "2024-01-20 10:00:00",
            "jobs_scraped": 150,
            "jobs_filtered": 150,
            "high_match": 8,
            "medium_match": 15,
            "auto_applied": 6,
            "pending_decision": 15,
            "failed": 2
        }
    """
    pass

# MCP Resources
@server.resource("resume://current")
async def get_current_resume() -> str:
    """返回当前简历内容"""
    pass

@server.resource("preferences://config")
async def get_preferences() -> str:
    """返回求职偏好配置"""
    pass

@server.resource("achievements://list")
async def get_achievements() -> str:
    """返回成就列表"""
    pass

@server.resource("jobs://pending")
async def get_pending_jobs() -> str:
    """返回待处理职位"""
    pass

if __name__ == "__main__":
    mcp.server.stdio.run_server(server)
```

### 6.3 Main Workflow (Claude Code Skill)

```markdown
<!-- .claude/skills/job-hunt.md -->
---
name: job-hunt
description: Execute the complete job hunting workflow
---

# Job Hunt Workflow

Execute the complete automated job hunting process:

## Step 1: Scrape New Jobs
Call `scrape_jobs(platform="all", limit=100)` to fetch new job listings.

## Step 2: Filter with GLM
Call `filter_jobs_with_glm()` to score all new jobs using the cheap GLM model.

## Step 3: Process High-Match Jobs (Auto-Apply)
For jobs with score >= 0.85:
1. Call `process_high_match_jobs()` which will:
   - Generate tailored resume
   - Auto-apply to each job
   - Record results

## Step 4: Handle Medium-Match Jobs
For jobs with score 0.60-0.85:
1. Call `get_pending_decisions()` to list them
2. Call `send_pending_decisions_to_telegram()` to notify user

## Step 5: Send Summary
Call `get_run_summary()` and `send_telegram_notification()` with:
- Total jobs scraped
- Jobs auto-applied
- Jobs pending user decision
- Any failures

## Usage
User can invoke with: `/job-hunt` or "开始求职任务"
```

---

## 7. Tech Stack Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Orchestrator** | Claude Code CLI | Main control, natural language interface |
| **Tool Interface** | MCP Server (Python) | Expose job hunting tools |
| **Filtering LLM** | GLM API | High-throughput, low-cost screening |
| **Decision/Tailoring LLM** | Claude API | High-quality decisions and resume generation |
| **Browser Automation** | Playwright (Headed) | Web scraping & form filling |
| **Database** | SQLite | Local persistence, deduplication |
| **PDF Generation** | WeasyPrint | Resume PDF creation |
| **Notifications** | python-telegram-bot | User notifications & decisions |
| **Configuration** | Markdown files | Human-readable config |

**Removed from original design:**
- ~~LangGraph~~ → Simple Python workflow
- ~~ChromaDB~~ → Claude reads markdown directly
- ~~Docker sandboxing~~ → Playwright browser contexts
- ~~Multiple LLM providers~~ → GLM (filter) + Claude (decision)
- ~~agent_tasks table~~ → Direct MCP tool calls

---

## 8. Project Structure

```
job_viewer/
├── src/
│   ├── mcp_server/           # MCP Server
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── scraper.py
│   │   │   ├── filter.py
│   │   │   ├── deduplicator.py
│   │   │   ├── decision.py
│   │   │   ├── tailor.py
│   │   │   ├── applier.py
│   │   │   └── notifier.py
│   │   └── resources/
│   │       └── ...
│   │
│   ├── core/                  # Core business logic
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── browser.py
│   │   ├── llm/
│   │   │   ├── glm_client.py
│   │   │   └── claude_client.py
│   │   ├── pdf_generator.py
│   │   └── telegram.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── markdown_parser.py
│       └── logging.py
│
├── config/                    # Configuration (Markdown)
│   ├── resume.md
│   ├── preferences.md
│   └── achievements.md
│
├── templates/
│   └── resume/
│       ├── modern.html
│       └── ats_friendly.html
│
├── data/
│   ├── jobs.db               # SQLite database
│   └── resumes/              # Generated PDFs
│
├── logs/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── .claude/
│   └── skills/
│       └── job-hunt.md       # Job hunt skill
│
├── .mcp.json                  # MCP server config
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 9. Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd job_viewer
python -m venv venv
.\venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env with your API keys:
# - GLM_API_KEY
# - ANTHROPIC_API_KEY
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID

# 4. Edit configuration files
# - config/resume.md (your resume)
# - config/preferences.md (job preferences)
# - config/achievements.md (your achievements)

# 5. Initialize database
python -m src.core.database init

# 6. Start Claude Code with MCP server
claude

# 7. Run job hunt
> /job-hunt
# or
> 开始今天的求职任务
```

---

## 10. Development Phases

### Phase 1: Foundation
- [x] Project structure setup
- [ ] SQLite database with deduplication
- [ ] Configuration markdown parser
- [ ] Basic MCP server skeleton

### Phase 2: Scraping
- [ ] Playwright LinkedIn scraper
- [ ] Playwright Indeed scraper
- [ ] Deduplication logic
- [ ] scrape_jobs tool

### Phase 3: Filtering
- [ ] GLM API client
- [ ] filter_jobs_with_glm tool
- [ ] Match scoring logic

### Phase 4: Decision & Apply
- [ ] Claude API client for tailoring
- [ ] Resume PDF generation
- [ ] Playwright job applier
- [ ] Auto-apply workflow

### Phase 5: Notifications
- [ ] Telegram bot setup
- [ ] Notification tools
- [ ] Pending decision workflow
- [ ] User approval handling

### Phase 6: Polish
- [ ] Error handling & retries
- [ ] Logging & monitoring
- [ ] Daily digest
- [ ] Testing

---

## 11. Environment Variables

```bash
# .env

# LLM APIs
GLM_API_KEY=your_glm_api_key
GLM_API_URL=https://api.glm.example.com/v1
ANTHROPIC_API_KEY=your_anthropic_api_key

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-xxx
TELEGRAM_CHAT_ID=123456789

# LinkedIn (for scraping)
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password

# Optional
INDEED_SESSION_COOKIE=xxx
PROXY_URL=http://user:pass@proxy:port
```

---

## 12. MCP Configuration

```json
// .mcp.json
{
  "mcpServers": {
    "job-hunter": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:\\Coding Life\\job_viewer",
      "env": {
        "GLM_API_KEY": "${GLM_API_KEY}",
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
        "TELEGRAM_BOT_TOKEN": "${TELEGRAM_BOT_TOKEN}",
        "TELEGRAM_CHAT_ID": "${TELEGRAM_CHAT_ID}"
      }
    }
  }
}
```

---

## Appendix: Decision Flow Pseudocode

```python
async def job_hunt_workflow():
    """Main workflow executed by Claude Code CLI"""

    # Create new run
    run = create_run()

    # Step 1: Scrape
    scrape_result = await scrape_jobs(platform="all", limit=100)
    run.jobs_scraped = scrape_result["new_jobs"]

    # Step 2: Filter with GLM (cheap)
    filter_result = await filter_jobs_with_glm()
    run.high_match = filter_result["high_match"]
    run.medium_match = filter_result["medium_match"]

    # Step 3: Auto-apply high match jobs
    high_match_jobs = await get_matched_jobs(min_score=0.85, status="matched")

    for job in high_match_jobs:
        # Check if not already applied
        if not await check_duplicate(job_id=job.id)["is_duplicate"]:
            # Tailor resume
            resume = await tailor_resume(job_id=job.id)
            # Apply
            result = await apply_to_job(job_id=job.id, resume_path=resume["pdf_path"])
            if result["status"] == "success":
                run.auto_applied += 1
            else:
                run.failed += 1

    # Step 4: Queue medium match for user decision
    medium_match_jobs = await get_matched_jobs(min_score=0.60, max_score=0.85, status="matched")

    for job in medium_match_jobs:
        job.status = "pending_decision"
        save_job(job)
        run.pending_decision += 1

    # Step 5: Notify user about pending decisions
    if run.pending_decision > 0:
        await send_pending_decisions_to_telegram()

    # Step 6: Send summary
    summary = f"""
    🎯 Job Hunt Complete!

    📊 Statistics:
    - Scraped: {run.jobs_scraped} new jobs
    - High Match (auto-applied): {run.auto_applied}
    - Medium Match (awaiting decision): {run.pending_decision}
    - Failed: {run.failed}

    Use /pending to review jobs awaiting your decision.
    """
    await send_telegram_notification(summary)

    return run
```

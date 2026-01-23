# Project Specification: AI-Powered Autonomous Job Search & Application System

## 1. Project Vision

To solve the time-constraint pain point in the job hunting process by developing a 24/7 autonomous agent system. The system acts as a "Digital Headhunter" that searches for, filters, and applies to high-quality AI/Backend remote roles in the US and Canada while the user is away from their computer.

---

## 2. System Architecture

The project follows a **Master-Subagent pattern** using a hierarchical state machine for orchestration.

### 2.1 Agent Definitions

| Agent | Technology | Responsibility |
|-------|------------|----------------|
| **Main Agent** | Claude Code CLI | High-level project manager. Reviews match reports, makes final "Apply/Skip" decisions, manages local file system for resume generation |
| **Filter Agent** | GLM-4.7 API | Initial heavy-duty JD screening. Uses GLM-4.7's high throughput to parse large volumes of jobs and identify high-potential leads |
| **Searcher Agent** | Playwright | Local script that 24/7 monitors LinkedIn, Wellfound, and Indeed using "Headed" mode on user's local machine |
| **Tailor Agent** | RAG + LLM | Dynamically adjusts resume bullet points based on JD requirements, focusing on user's key experiences |
| **Applier Agent** | Playwright Sandbox | Automates form-filling in isolated Docker environments for clean sessions and security |

### 2.2 Inter-Agent Communication Protocol

```
┌─────────────────────────────────────────────────────────────────┐
│                        SQLite (Shared State)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  jobs    │  │ applications│ │ resumes │  │ agent_tasks      │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
        ▲              ▲              ▲              ▲
        │              │              │              │
   ┌────┴────┐   ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
   │Searcher │   │  Filter   │  │  Tailor   │  │  Applier  │
   │  Agent  │   │   Agent   │  │   Agent   │  │   Agent   │
   └─────────┘   └───────────┘  └───────────┘  └───────────┘
                        ▲
                        │
                  ┌─────┴─────┐
                  │Main Agent │◄────► Telegram Bot
                  │(Claude)   │
                  └───────────┘
```

**Communication Method:** Database-driven task queue
- Agents poll `agent_tasks` table for pending work
- Status transitions: `pending` → `in_progress` → `completed` / `failed`
- Main Agent orchestrates by inserting tasks and monitoring completion
- Telegram Bot provides async human-in-the-loop interface

---

## 3. Core Technical Modules

### A. Data & Filtering (The Radar)

**Real-time Scraper:**
- Uses Playwright to extract structured job data (JD, Salary, Location, Visa support)
- Runs in headed mode for anti-detection
- Implements smart delays (2-5 seconds between actions)

**Semantic Screening:**
- GLM-4.7 analyzes cleaned DOM/Markdown versions of JD
- Determines if role fits "US/Canada Remote AI Engineer" criteria
- Outputs structured JSON with match score and reasoning

### B. Intelligent Tailoring (The Vault)

**RAG Knowledge Base:**
- ChromaDB instance stores "atomic" descriptions of user's career achievements
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (fast, good quality)
- Chunk strategy: One achievement = one chunk (with metadata tags)

**Contextual Matching:**
- Retrieves top-k relevant project blocks based on JD embedding similarity
- Example mappings:
  - AI roles → Vibe Coding, Newland AI Platform
  - Backend roles → Kafka, Global Relay LING
  - Full-stack → Both categories

**PDF Generation:**
- Library: WeasyPrint (HTML/CSS to PDF)
- Templates stored in `/templates/resume/`
- Supports multiple formats (1-page, 2-page, ATS-friendly)

### C. Execution & Sandboxing (The Executor)

**Stateful Orchestration:**
- Built with LangGraph for loops and error recovery
- Retry logic: 3 attempts with exponential backoff
- State persisted to SQLite for crash recovery

**Hermetic Sandboxing:**
- Each application runs in fresh Docker container
- Containers destroyed after use (no session leakage)
- Nginx reverse proxy for network isolation

### D. Remote Supervision (The Command Center)

**Telegram Bot Interface:**
- Library: `python-telegram-bot` (Polling mode to bypass NAT)
- Webhook alternative available for VPS deployment

**Bot Commands:**
| Command | Action |
|---------|--------|
| `/status` | Show pipeline stats (pending, approved, applied) |
| `/approve <job_id>` | Approve job for application |
| `/skip <job_id>` | Skip job permanently |
| `/pause` | Pause all agents |
| `/resume` | Resume agents |
| `/captcha` | Request manual CAPTCHA solving |
| `/daily` | Send daily digest summary |

**Notification Flow:**
1. New high-match job found → Send summary to user
2. Wait for response (timeout: 24 hours)
3. No response → Auto-skip and log
4. Approval → Queue for Tailor Agent

---

## 4. Database Schema

```sql
-- Core job data from scraping
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,           -- LinkedIn/Indeed job ID
    platform TEXT NOT NULL,            -- 'linkedin', 'wellfound', 'indeed'
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    jd_markdown TEXT,                  -- Cleaned job description
    jd_raw TEXT,                       -- Original HTML/text
    url TEXT NOT NULL,
    visa_sponsorship BOOLEAN,
    remote_type TEXT,                  -- 'full', 'hybrid', 'onsite'
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'new'          -- 'new', 'filtered', 'matched', 'rejected'
);

-- Filter agent results
CREATE TABLE filter_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    match_score REAL,                  -- 0.0 to 1.0
    match_reasoning TEXT,              -- LLM explanation
    key_requirements TEXT,             -- JSON array
    red_flags TEXT,                    -- JSON array
    filtered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Application tracking
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    resume_id INTEGER REFERENCES resumes(id),
    status TEXT DEFAULT 'pending',     -- 'pending', 'approved', 'applying', 'applied', 'failed', 'skipped'
    user_decision TEXT,                -- 'approve', 'skip', 'timeout'
    decision_at TIMESTAMP,
    applied_at TIMESTAMP,
    error_message TEXT,
    attempts INTEGER DEFAULT 0
);

-- Generated resumes
CREATE TABLE resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER REFERENCES jobs(id),
    pdf_path TEXT NOT NULL,
    template_used TEXT,
    bullets_used TEXT,                 -- JSON array of achievement IDs
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent task queue
CREATE TABLE agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,          -- 'searcher', 'filter', 'tailor', 'applier'
    task_type TEXT NOT NULL,           -- 'scrape', 'filter', 'generate_resume', 'apply'
    payload TEXT,                      -- JSON task data
    status TEXT DEFAULT 'pending',     -- 'pending', 'in_progress', 'completed', 'failed'
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result TEXT,                       -- JSON result data
    error TEXT
);

-- Audit log
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,                        -- 'info', 'warn', 'error'
    agent TEXT,
    message TEXT,
    details TEXT,                      -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Blacklist
CREATE TABLE blacklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,                         -- 'company', 'keyword', 'job_id'
    value TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Security & Credentials

### 5.1 Credential Management

| Secret | Storage Method |
|--------|----------------|
| LinkedIn credentials | `.env` file (gitignored) + environment variables |
| API keys (GLM, OpenAI) | `.env` file |
| Telegram bot token | `.env` file |
| Session cookies | Encrypted SQLite table or browser profile directory |

**Example `.env`:**
```
LINKEDIN_EMAIL=user@example.com
LINKEDIN_PASSWORD=<encrypted>
GLM_API_KEY=sk-xxx
OPENAI_API_KEY=sk-xxx
TELEGRAM_BOT_TOKEN=123456:ABC-xxx
TELEGRAM_CHAT_ID=123456789
```

### 5.2 Anti-Bot Detection Strategy

| Technique | Implementation |
|-----------|----------------|
| Realistic delays | Random 2-8 second delays between actions |
| Human-like mouse movement | Bezier curve mouse paths |
| Browser fingerprint | Use real Chrome profile, not headless |
| Session persistence | Reuse cookies across sessions when possible |
| IP management | Residential proxy rotation (optional) |
| Account warm-up | Gradual increase in activity over first week |
| Rate limiting | Max 50 job views per hour, 20 applications per day |

### 5.3 CAPTCHA Handling

1. **Detection:** Monitor for CAPTCHA elements in DOM
2. **Pause:** Stop automation immediately
3. **Notify:** Send screenshot to Telegram
4. **Wait:** User solves manually via remote desktop or provides solution
5. **Resume:** Continue automation after solve

---

## 6. Tech Stack Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| Master Orchestrator | Claude Code CLI / LangGraph | High-level decision making |
| Primary LLMs | GLM-4.7 (Filtering), GPT-4o / Claude 3.5 (Decision & Tailoring) | AI reasoning |
| Browser Automation | Playwright (Headed Mode) | Web scraping & form filling |
| Database | SQLite | Local persistence |
| Vector Store | ChromaDB | RAG knowledge base |
| Embeddings | sentence-transformers | Text embeddings |
| PDF Generation | WeasyPrint | Resume PDF creation |
| Infrastructure | Docker, Python 3.11+, FastAPI | Runtime environment |
| Notifications | python-telegram-bot | Remote supervision |
| Task Scheduling | APScheduler | Periodic job runs |

---

## 7. Configuration Management

### 7.1 Target Role Configuration (`config/targets.yaml`)

```yaml
job_search:
  titles:
    - "AI Engineer"
    - "ML Engineer"
    - "Backend Engineer"
    - "Software Engineer"
    - "Python Developer"

  locations:
    - "United States"
    - "Canada"
    - "Remote"

  remote_preference: "remote_only"  # 'remote_only', 'hybrid_ok', 'any'

  salary:
    min: 120000
    currency: "USD"

  experience_years:
    min: 2
    max: 10

  visa_required: true  # Only show jobs with visa sponsorship

filters:
  exclude_companies:
    - "Revature"
    - "Infosys"
    - "Wipro"

  exclude_keywords:
    - "clearance required"
    - "US citizen only"
    - "no sponsorship"

  require_keywords: []  # Any of these must appear

application:
  max_daily: 20
  max_hourly: 5
  auto_apply_threshold: 0.85  # Auto-apply if match score >= this
  notify_threshold: 0.60      # Notify user if score >= this
```

### 7.2 Resume Assets (`config/achievements.yaml`)

```yaml
achievements:
  - id: "newland-ai-platform"
    category: ["ai", "backend", "leadership"]
    title: "Newland AI Platform"
    bullets:
      - "Led development of enterprise AI platform serving 10K+ users"
      - "Implemented RAG pipeline reducing response latency by 40%"
    keywords: ["AI", "RAG", "LLM", "Python", "Leadership"]

  - id: "global-relay-ling"
    category: ["backend", "messaging"]
    title: "Global Relay LING"
    bullets:
      - "Architected high-throughput messaging system processing 1M+ events/day"
      - "Implemented Kafka-based event streaming with 99.9% uptime"
    keywords: ["Kafka", "Java", "Microservices", "Event-Driven"]

  # ... more achievements
```

---

## 8. Monitoring & Operations

### 8.1 Health Checks

| Check | Frequency | Alert Threshold |
|-------|-----------|-----------------|
| Searcher heartbeat | Every 5 min | No heartbeat for 15 min |
| Database size | Daily | > 1GB |
| API rate limits | Per request | > 80% of limit |
| Application success rate | Hourly | < 70% success |
| Pending tasks queue | Every 10 min | > 100 tasks |

### 8.2 Logging Strategy

```python
# Centralized logging configuration
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'level': 'INFO'},
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/agent.log',
            'maxBytes': 10_000_000,
            'backupCount': 5
        },
        'sqlite': {'class': 'custom.SQLiteHandler', 'table': 'logs'}
    },
    'loggers': {
        'searcher': {'level': 'DEBUG'},
        'filter': {'level': 'INFO'},
        'tailor': {'level': 'INFO'},
        'applier': {'level': 'DEBUG'}
    }
}
```

### 8.3 Metrics Dashboard

Key metrics to track:
- **Pipeline funnel:** Jobs scraped → Filtered → Matched → Applied
- **Success rates:** Application completion rate, response rate
- **LLM costs:** Token usage per agent, daily/weekly spend
- **Performance:** Average time per stage, bottleneck identification

---

## 9. Development Strategy (Phases)

### Phase 1: Foundation (Searcher + Filter + Notifications)
- [ ] Set up project structure and database schema
- [ ] Implement Playwright Searcher for LinkedIn
- [ ] Integrate GLM-4.7 for JD filtering
- [ ] Build Telegram bot with basic commands
- [ ] Add logging and error handling
- **Deliverable:** System can scrape jobs and notify user of matches

### Phase 2: Intelligence (RAG + Tailoring)
- [ ] Set up ChromaDB with achievement embeddings
- [ ] Build Tailor Agent with contextual matching
- [ ] Implement PDF resume generation
- [ ] Add resume preview to Telegram notifications
- **Deliverable:** System generates custom resumes per job

### Phase 3: Orchestration (Main Agent Integration)
- [ ] Integrate Claude Code CLI as Main Agent
- [ ] Implement LangGraph state machine
- [ ] Add decision logging and audit trail
- [ ] Build approval/skip workflow
- **Deliverable:** Full human-in-the-loop decision flow

### Phase 4: Automation (Applier + Error Handling)
- [ ] Implement Applier Agent with Docker sandboxing
- [ ] Add form-filling logic for common application formats
- [ ] Implement retry logic and error recovery
- [ ] Add Indeed and Wellfound support
- **Deliverable:** End-to-end autonomous application system

### Phase 5: Polish & Scale
- [ ] Build web dashboard for monitoring
- [ ] Add analytics and reporting
- [ ] Implement proxy rotation (optional)
- [ ] Performance optimization
- **Deliverable:** Production-ready system

---

## 10. Testing Strategy

### 10.1 Test Types

| Type | Scope | Tools |
|------|-------|-------|
| Unit tests | Individual functions | pytest |
| Integration tests | Agent interactions | pytest + mocks |
| E2E tests | Full workflow | Playwright + test accounts |
| Load tests | Rate limiting | locust |

### 10.2 Test Accounts

- Maintain separate LinkedIn/Indeed test accounts for E2E testing
- Use job postings from test companies or expired listings
- Never run E2E tests against production accounts

### 10.3 Mock Data

- Maintain fixtures for sample JDs, filter responses, resume outputs
- Use VCR.py to record and replay API responses

---

## 11. Legal & Compliance Considerations

### 11.1 Terms of Service

> **Disclaimer:** Automated access to job platforms may violate their Terms of Service. This system is designed for personal use and educational purposes. Users assume all responsibility for compliance with platform rules.

**Risk Mitigation:**
- Use headed browser (not headless) to appear more human-like
- Respect rate limits strictly
- Do not scrape or store personal data of other users
- Stop automation immediately if account is flagged

### 11.2 Data Retention

| Data Type | Retention Period | Deletion Method |
|-----------|------------------|-----------------|
| Job descriptions | 90 days | Automatic purge |
| Application history | Indefinite | Manual export/delete |
| Logs | 30 days | Automatic rotation |
| Generated resumes | 90 days | Automatic purge |

### 11.3 Privacy

- All data stored locally on user's machine
- No data transmitted to third parties except:
  - LLM APIs (JD text for filtering/tailoring)
  - Telegram (job summaries for notifications)
- User can export all data in JSON format
- User can delete all data via `/purge` command

---

## 12. Directory Structure

```
job_viewer/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── searcher.py
│   │   ├── filter.py
│   │   ├── tailor.py
│   │   └── applier.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── telegram_bot.py
│   │   └── handlers.py
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── migrations/
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embeddings.py
│   │   └── retriever.py
│   ├── resume/
│   │   ├── __init__.py
│   │   ├── generator.py
│   │   └── templates/
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       └── logging.py
├── config/
│   ├── targets.yaml
│   ├── achievements.yaml
│   └── settings.yaml
├── templates/
│   └── resume/
│       ├── modern.html
│       └── ats_friendly.html
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── logs/
├── data/
│   ├── jobs.db
│   └── chroma/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 13. Quick Start

```bash
# 1. Clone and setup
git clone <repo>
cd job_viewer
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Configure
cp .env.example .env
# Edit .env with your credentials and API keys

# 4. Initialize database
python -m src.db.init

# 5. Start agents
python -m src.agents.searcher  # In terminal 1
python -m src.bot.telegram_bot  # In terminal 2

# 6. Monitor
# Open Telegram and interact with your bot
```

---

## Appendix: Common Application Form Fields

Pre-configured responses for common application questions:

| Field | Value |
|-------|-------|
| Work authorization | "Yes, I require visa sponsorship" |
| Years of experience | Auto-calculated from resume |
| Willing to relocate | "Yes" if remote, "No" otherwise |
| Salary expectation | From config, or "Open to discussion" |
| Start date | "2 weeks notice" |
| LinkedIn URL | From config |
| Portfolio URL | From config |
| Cover letter | Auto-generated based on JD |

# Job Hunter AI - System Architecture

> **Last Updated:** 2026-01-30 (Production Release)

## Overview

Job Hunter AI uses a **hybrid architecture** combining MCP Server tools with Claude Code CLI orchestration. The system delegates visual scraping to Antigravity browser agent while automating data processing through MCP tools.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    USER (Job Seeker)                                         │
│                                                                              │
│   Natural Language Commands:                                                │
│   "Start job hunt", "Process new jobs", "Generate report"                   │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLAUDE CODE CLI (Project Manager)                         │
│                                                                              │
│   Orchestrates workflow, makes decisions, coordinates tools                 │
│   Pauses for manual tasks (Antigravity scraping)                            │
└────────────────────────────┬─────────────────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│  Antigravity    │  │  MCP Server      │  │  Local Storage      │
│  Browser Agent  │  │  (Automated)     │  │                     │
│                 │  │                  │  │  ├─ SQLite DB       │
│  Manual Tasks:  │  │  Tools:          │  │  ├─ JSON Files      │
│  ├─ Scrape jobs │  │  ├─ Generate     │  │  ├─ PDF Resumes    │
│  │  from visual │  │  │  instructions  │  │  └─ Markdown       │
│  │  platforms   │  │  ├─ Import JSON  │  │     Config          │
│  └─ Auto-apply  │  │  ├─ Filter jobs  │  │                     │
│     (future)    │  │  │  with GLM     │  │                     │
│                 │  │  └─ Generate     │  │                     │
│  User triggers  │  │     resumes      │  │                     │
│  via Claude     │  │                  │  │                     │
└─────────────────┘  └──────────────────┘  └─────────────────────┘
```

## Architecture Principles

### 1. Claude as Manager, Not Tool User

Claude Code CLI acts as a **project manager** that:
- Understands the overall workflow
- Decides when to use automated tools vs manual tasks
- Pauses for user confirmation on visual tasks
- Orchestrates multi-step processes

### 2. Hybrid Execution Model

**Automated (MCP Tools):**
- Instruction generation
- JSON import and deduplication
- AI filtering with GLM
- Resume generation

**Manual (Antigravity):**
- Visual platform scraping (LinkedIn, Glassdoor, Wellfound, Indeed)
- Form filling for applications (future)
- Tasks requiring browser interaction

**Why Manual for Scraping?**
- Current Playwright scrapers only work for LinkedIn
- Other platforms (Indeed, Glassdoor, Wellfound) are unreliable
- Antigravity visual agent is more robust for modern anti-bot measures
- User maintains control over account logins

### 3. Data Sources Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Sources                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Priority 1: ATS Platforms (Highest Quality)                    │
│  ├─ Greenhouse                                                   │
│  ├─ Lever                [PLANNED - Task 6]                      │
│  ├─ Ashby                                                        │
│  └─ Workable                                                     │
│     └─ Method: Google dorking (automated, no Antigravity)       │
│                                                                  │
│  Priority 2: Visual Job Boards (High Volume)                    │
│  ├─ LinkedIn                                                     │
│  ├─ Glassdoor            [IMPLEMENTED - Tasks 3-5]              │
│  ├─ Wellfound                                                    │
│  └─ Indeed                                                       │
│     └─ Method: Antigravity browser agent (manual trigger)       │
│                                                                  │
│  Priority 3+: Other Sources (Future)                            │
│  ├─ RSS Feeds            [FUTURE]                               │
│  ├─ Company career pages [FUTURE]                               │
│  └─ Telegram channels    [FUTURE]                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Daily Workflow

```
1. MORNING: Generate Instructions
   ┌─────────────────────────────────────┐
   │ User: "Start job hunt"              │
   │                                     │
   │ Claude → MCP Tool:                  │
   │   generate_antigravity_scraping_    │
   │   guide()                           │
   │   ├─ Reads config/preferences.md    │
   │   │   (24 job titles, filters)      │
   │   ├─ Reads config/credentials.md    │
   │   └─ Generates instructions/        │
   │      scrape_jobs_2026-01-29.json    │
   │                                     │
   │ Claude: "Please run Antigravity:"   │
   │   antigravity run instructions/...  │
   │                                     │
   │ User: [Runs Antigravity - 5 min]   │
   │   → Scrapes 150+ jobs               │
   │   → Saves to data/*.json            │
   └─────────────────────────────────────┘
                  ↓
2. AUTOMATED: Import & Deduplicate
   ┌─────────────────────────────────────┐
   │ User: "Done scraping"               │
   │                                     │
   │ Claude → MCP Tool:                  │
   │   import_antigravity_results()      │
   │   ├─ Scans data/*.json              │
   │   ├─ Deduplication (2 levels):      │
   │   │   1. URL exact match            │
   │   │   2. Fuzzy hash (company+title) │
   │   ├─ Source priority handling       │
   │   │   (ATS=1 > Visual=2 > Other=3)  │
   │   └─ Imports to SQLite              │
   │                                     │
   │ Result: 150 scraped → 120 unique    │
   └─────────────────────────────────────┘
                  ↓
3. AUTOMATED: AI Filtering
   ┌─────────────────────────────────────┐
   │ Claude → MCP Tool:                  │
   │   process_jobs_with_glm_tool()      │
   │   ├─ Loads config/achievements.md   │
   │   ├─ Loads config/preferences.md    │
   │   └─ For each unprocessed job:      │
   │       ├─ GLM scores 0-100           │
   │       └─ Three-tier routing:        │
   │           ├─ ≥85: Tier 1 HIGH       │
   │           ├─ 60-84: Tier 2 MEDIUM   │
   │           └─ <60: Tier 3 LOW        │
   │                                     │
   │ Tier 1 (8 jobs):                    │
   │   → Auto-generate PDF resumes       │
   │   → Status: matched (auto)          │
   │                                     │
   │ Tier 2 (18 jobs):                   │
   │   → Add to campaign report          │
   │   → Status: matched (manual)        │
   │                                     │
   │ Tier 3 (94 jobs):                   │
   │   → Archive, no action              │
   │   → Status: rejected                │
   │                                     │
   │ Cost: ~$0.03 for 120 jobs           │
   └─────────────────────────────────────┘
                  ↓
4. EVENING: Review & Apply
   ┌─────────────────────────────────────┐
   │ Claude: "Report ready"              │
   │   → 8 HIGH matches (resumes ready)  │
   │   → 18 MEDIUM matches (need review) │
   │                                     │
   │ User: Reviews, approves some        │
   │                                     │
   │ Claude → Generate application       │
   │          instructions (Task 8)      │
   │                                     │
   │ User: [Runs Antigravity to apply]   │
   │   → Auto-fills forms                │
   │   → Pauses at Submit button         │
   └─────────────────────────────────────┘
```

### Three-Tier Scoring System

```
                    GLM Filtering (0-100 score)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   Score ≥ 85            60 ≤ Score < 85        Score < 60
        │                     │                     │
        ▼                     ▼                     ▼
   TIER 1: HIGH          TIER 2: MEDIUM        TIER 3: LOW
        │                     │                     │
        ▼                     ▼                     ▼
  Auto-generate        Add to campaign         Auto-archive
  PDF resume           report for review       (no action)
        │                     │
        ▼                     ▼
  status='matched'      status='matched'
  decision='auto'       decision='manual'
        │                     │
        └─────────┬───────────┘
                  ▼
           Ready to Apply
```

## Directory Structure (Current)

```
JobHunterAI/
├── src/
│   ├── agents/                   # Instruction Generators [NEW]
│   │   ├── __init__.py
│   │   ├── instruction_generator.py      # Task 3: Antigravity scraping guide
│   │   ├── platform_configs.py           # Platform-specific templates
│   │   └── application_guide_generator.py [PLANNED - Task 8]
│   │
│   ├── mcp_server/              # MCP Server (Claude Code integration)
│   │   ├── __init__.py
│   │   ├── server.py            # Main MCP server entry
│   │   └── tools/               # MCP Tool implementations
│   │       ├── __init__.py
│   │       ├── antigravity.py   # Task 3: generate_antigravity_scraping_guide
│   │       ├── importer.py      # Task 4: import_antigravity_results
│   │       ├── gl_processor.py  # Task 5: process_jobs_with_glm_tool
│   │       ├── ats_scanner.py   [PLANNED - Task 6]
│   │       └── report.py        [PLANNED - Task 7]
│   │
│   ├── core/                    # Core business logic
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite with source tracking [UPDATED]
│   │   ├── importer.py          # Task 4: JSON → DB with dedup [NEW]
│   │   ├── gl_processor.py      # Task 5: GLM filtering engine [NEW]
│   │   ├── pdf_generator.py     # Resume PDF generation
│   │   └── llm/
│   │       ├── __init__.py
│   │       ├── glm_client.py    # GLM API client
│   │       └── claude_client.py # Claude API client
│   │
│   ├── scrapers/                # [DEPRECATED - Use Antigravity]
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── linkedin.py          # Only LinkedIn works
│   │
│   ├── output/                  # Output generators
│   │   └── report_generator.py  [PLANNED - Task 7]
│   │
│   └── utils/
│       ├── __init__.py
│       ├── config.py            # Configuration loader
│       ├── markdown_parser.py   # Parse config/*.md
│       └── logger.py            # Logging setup
│
├── config/                      # User configuration (Markdown) [GITIGNORED]
│   ├── resume.md                # Resume content
│   ├── preferences.md           # Job criteria (24 titles, filters)
│   ├── achievements.md          # Career highlights
│   └── credentials.md           # Platform logins
│
├── instructions/                # Generated Antigravity guides [NEW]
│   └── scrape_jobs_YYYY-MM-DD.json
│
├── campaigns/                   # Daily campaign reports [NEW]
│   └── campaign_YYYY-MM-DD.md   [PLANNED - Task 7]
│
├── data/                        # Runtime data [GITIGNORED]
│   ├── jobs.db                  # SQLite database
│   ├── linkedin_2026-01-29.json # Scraped data from Antigravity
│   ├── glassdoor_2026-01-29.json
│   └── ...
│
├── output/                      # Generated resumes [GITIGNORED]
│   ├── Scribd_AI_Engineer.pdf
│   └── ...
│
├── templates/                   # HTML templates
│   └── resume/
│       └── modern.html          # Resume template
│
├── archive/                     # Archived/deprecated code
│   └── old_scrapers/            # Deprecated Playwright scrapers
│
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md          # This file
│   ├── DEVELOPMENT_GUIDE.md     # Technical guide for sub-agents
│   └── CLEANUP_AND_GUIDE_SUMMARY.md
│
├── scripts/                     # Utility scripts
│   ├── migrate_add_source_tracking.py
│   └── migrate_add_fuzzy_hash.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── .env                         # API keys [GITIGNORED]
├── .env.example                 # Environment template
├── .gitignore
├── requirements.txt
├── README.md                    # User-friendly guide
└── pyproject.toml
```

## Technology Stack

| Component | Technology | Purpose | Status |
|-----------|------------|---------|--------|
| **Orchestrator** | Claude Code CLI | Project manager, workflow control | ✅ Active |
| **Tool Interface** | MCP Server (Python) | Expose tools to Claude | ✅ Active |
| **Visual Agent** | Antigravity | Browser scraping, form filling | ✅ Active |
| **Filtering LLM** | GLM API (智谱AI) | Cost-effective job filtering | ✅ Active |
| **Resume LLM** | Claude API (Anthropic) | High-quality resume tailoring | ✅ Active |
| **Database** | SQLite (WAL mode) | Local job storage | ✅ Active |
| **PDF Generator** | WeasyPrint | Resume PDF generation | ✅ Active |
| **Config Format** | Markdown | Human-readable configuration | ✅ Active |
| **Browser (deprecated)** | Playwright | Old scraping method | ⚠️ LinkedIn only |

## Database Schema

### Jobs Table (Updated)

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,           -- Platform job ID
    url TEXT NOT NULL,
    url_hash TEXT,                     -- MD5(url) for exact dedup
    fuzzy_hash TEXT,                   -- MD5(company+title) for fuzzy dedup
    source TEXT DEFAULT 'linkedin',    -- [NEW] Platform source
    source_priority INTEGER DEFAULT 2, -- [NEW] ATS=1, Visual=2, Other=3

    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    description TEXT,
    posted_date TEXT,

    ai_score REAL,                     -- GLM score (0-100)
    ai_reasoning TEXT,                 -- Why this score?
    is_processed BOOLEAN DEFAULT 0,    -- [NEW] Has GLM filtered?

    status TEXT DEFAULT 'pending',     -- pending|matched|rejected|applied
    decision_type TEXT,                -- auto|manual (for matched jobs)

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_url_hash ON jobs(url_hash);
CREATE INDEX idx_jobs_fuzzy_hash ON jobs(fuzzy_hash);
CREATE INDEX idx_jobs_source ON jobs(source);
CREATE INDEX idx_jobs_is_processed ON jobs(is_processed);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_ai_score ON jobs(ai_score);
```

### Deduplication Strategy

**Two-Level Deduplication:**

1. **Level 1: URL Exact Match**
   - Hash: `MD5(url)`
   - Catches same job reposted

2. **Level 2: Fuzzy Hash**
   - Hash: `MD5(company.lower() + title.lower())`
   - Catches same job across platforms
   - Example: "Senior Engineer at Google" on LinkedIn vs Indeed

**Source Priority on Conflict:**
- When fuzzy match found, keep higher priority:
  - ATS platforms (priority=1) > Visual platforms (priority=2) > Others (priority=3)
- Reasoning: ATS job postings are most accurate (direct from company)

## MCP Tools (Current Implementation)

### Implemented (Phase 2 - Tasks 3-5)

```python
# Task 3: Antigravity Instruction Generator
@server.tool()
async def generate_antigravity_scraping_guide(
    date: str = None  # Optional, defaults to today
) -> dict:
    """
    Generates JSON instruction file for Antigravity browser agent.

    Reads:
    - config/preferences.md (24 job titles, locations, filters)
    - config/credentials.md (login credentials for auto-login)

    Outputs:
    - instructions/scrape_jobs_{date}.json

    Returns:
        {
            "instruction_file": "instructions/scrape_jobs_2026-01-29.json",
            "platforms": ["linkedin", "glassdoor", "wellfound", "indeed"],
            "job_titles": 24,
            "message": "Please run: antigravity run {instruction_file}"
        }
    """

# Task 4: JSON Importer with Deduplication
@server.tool()
async def import_antigravity_results(
    files: list = None  # Optional, defaults to data/*.json
) -> dict:
    """
    Imports scraped JSON files to database with two-level deduplication.

    Deduplication:
    1. URL exact match (url_hash)
    2. Fuzzy match (company + title)
    3. Source priority resolution (ATS > Visual > Other)

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
                "glassdoor": {"total": 40, "new": 30},
                ...
            }
        }
    """

# Task 5: GLM Processor with Three-Tier Scoring
@server.tool()
async def process_jobs_with_glm_tool(
    force_reprocess: bool = False  # Re-process already filtered jobs
) -> dict:
    """
    Processes unfiltered jobs with GLM and routes to three tiers.

    Scoring:
    - Reads config/achievements.md (career highlights)
    - Reads config/preferences.md (job criteria)
    - GLM scores each job 0-100

    Routing:
    - Score ≥85: Tier 1 HIGH → Auto-generate resume
    - 60≤ Score <85: Tier 2 MEDIUM → Add to campaign report
    - Score <60: Tier 3 LOW → Archive

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

### Planned (Phase 3 - Tasks 6-8)

```python
# Task 6: ATS Dorking Scanner
@server.tool()
async def scan_ats_platforms(
    max_results_per_platform: int = 50
) -> dict:
    """
    Automated Google dorking for ATS platforms.
    No Antigravity needed - direct scraping.

    Platforms: Greenhouse, Lever, Ashby, Workable
    """

# Task 7: Campaign Report Generator
@server.tool()
async def generate_campaign_report(
    date: str = None
) -> dict:
    """
    Generates Markdown campaign report with:
    - HIGH MATCH jobs (Tier 1) with resume links
    - MEDIUM MATCH jobs (Tier 2) for user review
    - Statistics and cost breakdown
    """

# Task 8: Application Instruction Generator
@server.tool()
async def generate_application_instructions(
    campaign_date: str = None
) -> dict:
    """
    Generates JSON instructions for Antigravity to auto-apply.
    User reviews and approves before running.
    """
```

## Key Design Decisions

### 1. Why Antigravity for Visual Platforms?

**Problem:** Current Playwright scrapers fail for Indeed, Glassdoor, Wellfound
- Anti-bot detection improves constantly
- Maintaining platform-specific scrapers is high effort
- Login sessions expire frequently

**Solution:** Antigravity browser agent
- Visual agent understands web pages like humans
- More resilient to UI changes
- User maintains control over logins
- Manual trigger = user awareness

**Trade-off:** Manual trigger required (~5 min/day)
**Benefit:** Higher reliability, less maintenance

### 2. Why Hybrid MCP + CLI?

**MCP Server:** Automated tools that run without user intervention
- JSON import (no decisions needed)
- GLM filtering (follows clear rules)
- Resume generation (template-based)

**Claude CLI:** Orchestration and decision-making
- Understands overall workflow
- Pauses for manual tasks
- Makes judgment calls
- Provides context to user

**Alternative Considered:** Pure MCP without CLI
**Rejected Because:** Would automate too much, user loses visibility

### 3. Why Three-Tier Scoring?

**Tier 1 (≥85):** High confidence → Auto-generate resume
- Saves user time on obvious matches
- Still requires manual submit

**Tier 2 (60-84):** Medium confidence → User review
- Edge cases need human judgment
- Example: Great match but contract role

**Tier 3 (<60):** Low match → Archive
- Keeps database clean
- User can still review if curious

**Alternative Considered:** Binary yes/no
**Rejected Because:** Loses nuance, can't prioritize

### 4. Why Two-Level Deduplication?

**Level 1 (URL):** Catches exact reposts
**Level 2 (Fuzzy):** Catches cross-platform duplicates

**Why Both?**
- Same company posts on LinkedIn and Indeed
- Want one application, not two
- Keep ATS version (priority=1) over scraped version

**Alternative Considered:** URL only
**Rejected Because:** Misses cross-platform duplicates

### 5. Why Markdown Config?

**Pros:**
- Human-readable (non-technical users can edit)
- Easy to version control
- AI can understand context better
- No learning curve

**Cons:**
- Less structured than JSON
- Parsing is more complex

**Decision:** User experience over developer convenience

## Cost Analysis

### Daily Operations (50 jobs/day)

| Service | Usage | Unit Cost | Daily Cost |
|---------|-------|-----------|------------|
| **GLM API** | 50 job filters | ~$0.001/job | $0.05 |
| **Claude API** | 8 resumes | ~$0.02/resume | $0.16 |
| **Total** | - | - | **$0.21/day** |

### Monthly: ~$6.30
### Compare to:
- Job board premium: $30-100/month
- Manual search time: 10+ hours/week (priceless)

## Current Implementation Status

### ✅ Phase 1: Foundation (Tasks 1-2)
- [x] Database schema with source tracking
- [x] Fuzzy hash deduplication
- [x] Migration scripts
- [x] Archive old scrapers

### ✅ Phase 2: Core Features (Tasks 3-5) - 62.5% Complete
- [x] Task 3: Antigravity instruction generator
  - Reads preferences.md (24 job titles)
  - Reads credentials.md (auto-login)
  - Generates JSON for Antigravity
- [x] Task 4: JSON importer
  - Two-level deduplication
  - Source priority handling
  - Batch import support
- [x] Task 5: GLM processor
  - Three-tier scoring (85/60 thresholds)
  - Auto-resume generation for Tier 1
  - Cost tracking

### ⏸️ Phase 3: Enhancements (Tasks 6-8) - 37.5% Remaining
- [ ] Task 6: ATS dorking scanner
  - Google search automation
  - Greenhouse, Lever, Ashby, Workable
  - Priority=1 source
- [ ] Task 7: Campaign report generator
  - Markdown tables
  - HIGH/MEDIUM sections
  - Statistics dashboard
- [ ] Task 8: Application instruction generator
  - JSON for Antigravity auto-apply
  - Form filling templates
  - User approval workflow

**Current system is production-ready for daily use.** Phase 3 adds polish and automation.

## Security & Privacy

### Data Privacy
- All data stored locally (SQLite)
- No cloud uploads except API calls
- API calls are job descriptions only (no personal data)
- Credentials stored in gitignored files

### Gitignored Files
```
config/resume.md
config/preferences.md
config/achievements.md
config/credentials.md
.env
data/jobs.db
data/*.json
output/*.pdf
```

### API Key Usage
- **GLM API:** Job filtering only (receives job descriptions)
- **Claude API:** Resume generation (receives job descriptions + your achievements)
- Never shared externally
- You control when to call APIs

## Testing Strategy

### Unit Tests
```
tests/unit/
├── test_database.py       # DB operations
├── test_importer.py       # Deduplication logic
├── test_gl_processor.py   # Scoring logic
└── test_instruction_gen.py # JSON generation
```

### Integration Tests
```
tests/integration/
├── test_workflow.py       # End-to-end daily workflow
├── test_mcp_tools.py      # MCP tool integration
└── test_antigravity.py    # Antigravity integration (manual)
```

### Manual Testing
```bash
# Test instruction generation
python -m src.agents.instruction_generator

# Test import
python -m src.core.importer data/linkedin_test.json

# Test GLM processing
python -m src.core.gl_processor --limit 5
```

## Troubleshooting

### Common Issues

**1. "No jobs imported" after Antigravity run**
- Check data/*.json files exist
- Verify JSON format matches expected schema
- Check database connection

**2. "GLM API error: rate limit"**
- Wait 60 seconds between batches
- Reduce batch size in gl_processor.py
- Check API key quota

**3. "Antigravity login failed"**
- Update credentials.md with current passwords
- Check if accounts are locked
- Manually log in first to verify

**4. "Resume generation failed"**
- Check config/resume.md exists and is valid
- Verify Claude API key in .env
- Check template file templates/resume/modern.html

## Development Workflow

### Adding a New Platform

1. **Add platform config** to `src/agents/platform_configs.py`
2. **Update preferences.md** template with new platform
3. **Test with Antigravity** manually first
4. **Add to instruction generator** logic
5. **Document** in this file

### Adding a New MCP Tool

1. **Create tool file** in `src/mcp_server/tools/`
2. **Register in server.py** with `@server.tool()`
3. **Add unit tests** in `tests/unit/`
4. **Document in DEVELOPMENT_GUIDE.md**
5. **Update this ARCHITECTURE.md**

## Future Enhancements

### Considered for Future Phases

**Phase 4: Analytics**
- Response rate tracking
- Interview conversion metrics
- Best platforms/time analysis

**Phase 5: Advanced Automation**
- Interview scheduling automation
- Follow-up email templates
- Offer comparison dashboard

**Phase 6: Multi-User**
- Team job hunting
- Shared job pool
- Collaborative filtering

## References

- **README.md** - User guide and quick start
- **docs/DEVELOPMENT_GUIDE.md** - Technical implementation details
- **.claude/skills/job-hunt/SKILL.md** - Claude CLI skill documentation

---

**Last Updated:** 2026-01-29
**Status:** Phase 2 Complete (62.5%)
**Next Step:** Task 6 (ATS Dorking Scanner)

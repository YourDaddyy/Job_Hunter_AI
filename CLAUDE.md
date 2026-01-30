# Job Hunter AI - Agent Guide

> **This file is auto-read by Claude Code. When user says "start job hunt" or similar, follow this workflow.**

## Quick Start Commands

When user wants to start job hunting, they may say:
- "start job hunt"
- "find jobs"
- "run daily job search"
- "/job-hunt"

## System Status Check

Before starting, verify the system is ready:

```python
# Quick check (run this first)
import sqlite3
conn = sqlite3.connect('data/jobs.db')
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM jobs")
print(f"Database ready: {c.fetchone()[0]} jobs")
conn.close()
```

**Required files:**
- `config/preferences.md` - Job titles, salary, location requirements
- `config/achievements.md` - Career highlights for AI matching
- `config/credentials.md` - Platform login credentials
- `.env` - API keys (GLM_API_KEY required, ANTHROPIC_API_KEY optional)

## Daily Workflow (Execute in Order)

### Step 1: Generate Scraping Instructions

```bash
cd "." && python -m src.agents.instruction_generator
```

**Output:** Creates `instructions/scrape_jobs_YYYY-MM-DD.json`

**Tell user (copy-paste ready prompt for Antigravity):**

```
Scraping instructions generated!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━�?
COPY THIS TO ANTIGRAVITY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━�?
/turbo-all Run job search using W:\Code\job_viewer\instructions\scrape_jobs_YYYY-MM-DD.json

Log into LinkedIn, Indeed, Wellfound, Glassdoor and search for AI/ML/SDET roles (24 job titles). Filter for Remote/Canada. Save results to W:\Code\job_viewer\data\ as JSON files.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━�?

Estimated time: 5-10 minutes

Come back and say "done" when finished, or "skip" to use existing data.
```

### Step 2: Wait for User (PAUSE HERE)

User will either:
- Run Antigravity and say "done"
- Say "skip" to skip scraping
- Report errors (help troubleshoot)

### Step 3: Import Scraped Data

```bash
cd "." && python -c "
from src.core.importer import AntigravityImporter
importer = AntigravityImporter()
result = importer.import_from_directory('data/')
print(f'Imported: {result}')
"
```

**Alternative - ATS Scanner (no browser needed):**
```bash
cd "." && python -m src.scrapers.ats_scanner
```

### Step 4: Filter with AI (GLM)

```bash
cd "." && python -c "
from src.core.gl_processor import GLMProcessor
processor = GLMProcessor()
result = processor.process_unscored_jobs()
print(f'Processed: {result}')
"
```

**Expected output:**
- HIGH MATCH (>=85): Auto-generate resumes
- MEDIUM MATCH (60-84): User review needed
- LOW MATCH (<60): Auto-rejected

### Step 5: Generate Campaign Report

```bash
cd "." && python -c "
from src.output.report_generator import CampaignReportGenerator
gen = CampaignReportGenerator()
result = gen.generate_report()
print(f'Report: {result}')
"
```

**Output:** Creates `campaigns/campaign_YYYY-MM-DD.md`

### Step 6: Show Results to User

Read the campaign report and summarize:
- Number of HIGH match jobs (resumes ready)
- Number of MEDIUM match jobs (need review)
- Total cost estimate
- Next steps

## Database Quick Queries

```python
import sqlite3
conn = sqlite3.connect('data/jobs.db')

# High matches (auto-apply ready)
c.execute("""
    SELECT company, title, ai_score, url
    FROM jobs
    WHERE status='matched' AND decision_type='auto'
    ORDER BY ai_score DESC LIMIT 10
""")

# Medium matches (need review)
c.execute("""
    SELECT company, title, ai_score, ai_reasoning
    FROM jobs
    WHERE status='matched' AND decision_type='manual'
    ORDER BY ai_score DESC LIMIT 10
""")

# Today's stats
c.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status='matched' THEN 1 ELSE 0 END) as matched,
        SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected
    FROM jobs WHERE DATE(created_at) = DATE('now')
""")
```

## Error Handling

### "No jobs found"
- Check if `data/*.json` files exist
- Try running ATS scanner as alternative
- Check if database is initialized

### "GLM API error"
- Check `GLM_API_KEY` in `.env`
- Check API quota at https://open.bigmodel.cn/

### "Antigravity failed"
- Check credentials in `config/credentials.md`
- Try manual login to clear CAPTCHAs
- Suggest running ATS scanner instead

## User's Profile Summary

> **Note:** This section shows example values. Actual preferences are loaded from config files.

**Target Roles:**
- Configured in `config/preferences.md`

**Location:** Configured in `config/preferences.md`

**Salary:** Configured in `config/preferences.md`

**Key Skills:**
- Configured in `config/resume.md` and `config/achievements.md`

## File Locations

| Purpose | Location |
|---------|----------|
| Job database | `data/jobs.db` |
| Config files | `config/*.md` |
| Generated resumes | `output/*.pdf` |
| Scraping instructions | `instructions/scrape_jobs_*.json` |
| Campaign reports | `campaigns/campaign_*.md` |
| API keys | `.env` |

## Cost Estimates

- GLM filtering: ~$0.001/job
- Resume generation: ~$0.003/resume (default: GLM, configurable in `config/llm_providers.md`)
- Typical daily run: ~$0.15-0.20

**LLM Providers:** Configure in `config/llm_providers.md` - supports GLM, OpenAI, Gemini, Claude, OpenRouter

## MCP Server

The MCP server provides automated tools. Config in `.mcp.json`:
- `generate_antigravity_scraping_guide`
- `import_antigravity_results`
- `process_jobs_with_glm_tool`
- `generate_campaign_report_tool`
- `scan_ats_platforms_tool`

Start MCP server: `python -m src.mcp_server.server`

## Workflow Modes

### Full Workflow (with Antigravity)
1. Generate instructions -> User runs Antigravity -> Import -> Filter -> Report

### Quick Mode (ATS only, no browser)
1. Run ATS scanner -> Filter -> Report
```bash
python -m src.core.ats_scanner && python -m src.core.glm_processor
```

### Reprocess Mode (existing jobs only)
1. Filter unprocessed jobs -> Report
```bash
python -c "from src.core.glm_processor import GLMProcessor; GLMProcessor().process_unscored_jobs()"
```

## Notes for Claude

- Always check database status before starting
- User is based in Canada, looking for remote work
- Prefer ATS scanner if user doesn't have Antigravity
- Resume generation needs valid ANTHROPIC_API_KEY
- Show cost estimates when processing
- Summarize results clearly at end

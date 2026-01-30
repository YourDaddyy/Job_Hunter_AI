# Job Hunter AI - Development Guide

> **For Sub-Agents and Developers**
> **Last Updated:** 2026-01-29
> **Status:** Phase 2 Complete (62.5% implementation)

This guide provides technical implementation details for developers and sub-agents working on the Job Hunter AI project.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [What's Implemented (Tasks 1-5)](#whats-implemented-tasks-1-5)
3. [What's Remaining (Tasks 6-8)](#whats-remaining-tasks-6-8)
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

## What's Implemented (Tasks 1-5)

### ✅ Phase 1: Foundation (Tasks 1-2)

#### Task 1: Database Enhancement

**File:** `src/core/database.py`

**Changes:**
- Added `source` column (platform identifier)
- Added `source_priority` column (ATS=1, Visual=2, Other=3)
- Added `is_processed` column (GLM filtering status)
- Added `fuzzy_hash` column (company+title hash for cross-platform dedup)

**Migration Scripts:**
- `scripts/migrate_add_source_tracking.py`
- `scripts/migrate_add_fuzzy_hash.py`

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

**Archived Files:**
- `archive/old_scrapers/applier.py` (Playwright applier - deprecated)
- `archive/old_scrapers/indeed.py` (Playwright scraper - broken)
- `archive/old_scrapers/wellfound.py` (Playwright scraper - broken)

**Reason:** Current Playwright scrapers only work for LinkedIn. Indeed, Glassdoor, Wellfound scrapers fail due to anti-bot measures. Solution: Use Antigravity visual agent instead.

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

Uses Claude API to:
1. Read `config/resume.md` (base resume)
2. Read `config/achievements.md` (achievement pool)
3. Analyze job description
4. Select relevant achievements
5. Tailor resume content
6. Generate PDF using `src/core/pdf_generator.py`

**Cost Tracking:**
- GLM API: ~$0.001 per job
- Claude API (resume): ~$0.02 per resume
- Example: 120 jobs → $0.03 (GLM) + $0.16 (8 resumes) = $0.19

---

## What's Remaining (Tasks 6-8)

### ⏸️ Task 6: ATS Dorking Scanner

**Goal:** Automated Google dorking to find jobs on ATS platforms.

**Target Platforms:**
- Greenhouse (jobs.greenhouse.io)
- Lever (jobs.lever.co)
- Ashby (jobs.ashbyhq.com)
- Workable (apply.workable.com)

**Why ATS Platforms?**
- Highest quality (direct from company)
- More complete job descriptions
- Higher priority (source_priority=1)
- No account login needed

**Implementation Plan:**

**File:** `src/scrapers/ats_scanner.py`

```python
class ATSScanner:
    """
    Google dorking scanner for ATS platforms.
    No Antigravity needed - direct scraping.
    """

    ATS_PLATFORMS = {
        'greenhouse': {
            'domain': 'jobs.greenhouse.io',
            'url_pattern': 'https://jobs.greenhouse.io/{company}/jobs/{id}',
            'priority': 1
        },
        'lever': {
            'domain': 'jobs.lever.co',
            'url_pattern': 'https://jobs.lever.co/{company}/{id}',
            'priority': 1
        },
        'ashby': {
            'domain': 'jobs.ashbyhq.com',
            'url_pattern': 'https://jobs.ashbyhq.com/{company}/{id}',
            'priority': 1
        },
        'workable': {
            'domain': 'apply.workable.com',
            'url_pattern': 'https://apply.workable.com/{company}/j/{id}',
            'priority': 1
        }
    }

    async def dork_google(
        self,
        job_title: str,
        platform: str,
        max_results: int = 50
    ) -> list[dict]:
        """
        Google dork for ATS jobs.

        Example query:
        site:jobs.greenhouse.io "AI Engineer" "Remote" -expired

        Returns:
            List of job URLs found
        """
        query = self._build_dork_query(job_title, platform)
        results = await self._search_google(query, max_results)
        return results

    async def scrape_ats_job(
        self,
        url: str,
        platform: str
    ) -> dict:
        """
        Scrape job details from ATS page.

        ATS pages are clean HTML, easy to parse.
        """
        html = await fetch_url(url)
        soup = BeautifulSoup(html, 'html.parser')

        # Extract based on platform
        if platform == 'greenhouse':
            title = soup.select_one('.app-title').text
            company = soup.select_one('.company-name').text
            description = soup.select_one('#content').text
        # ... other platforms

        return {
            'title': title,
            'company': company,
            'url': url,
            'description': description,
            'source': platform,
            'source_priority': 1  # ATS platforms highest priority
        }
```

**MCP Tool:**

**File:** `src/mcp_server/tools/ats_scanner.py`

```python
@server.tool()
async def scan_ats_platforms(
    job_titles: list = None,  # Optional, defaults from preferences.md
    max_results_per_platform: int = 50
) -> dict:
    """
    Automated ATS platform scanning via Google dorking.

    Args:
        job_titles: List of job titles to search (default from preferences)
        max_results_per_platform: Max results per ATS platform

    Returns:
        {
            "total_found": 45,
            "total_new": 30,
            "by_platform": {
                "greenhouse": {"found": 15, "new": 10},
                "lever": {"found": 12, "new": 8},
                "ashby": {"found": 10, "new": 7},
                "workable": {"found": 8, "new": 5}
            },
            "cost_usd": 0.00,  # No API cost, just scraping
            "duration_seconds": 45
        }
    """
    scanner = ATSScanner()

    if not job_titles:
        prefs = load_preferences()
        job_titles = prefs['job_titles']

    results = {
        "total_found": 0,
        "total_new": 0,
        "by_platform": {}
    }

    for platform in ['greenhouse', 'lever', 'ashby', 'workable']:
        for job_title in job_titles:
            # Google dork
            urls = await scanner.dork_google(
                job_title,
                platform,
                max_results_per_platform
            )

            # Scrape each URL
            for url in urls:
                job_data = await scanner.scrape_ats_job(url, platform)

                # Import to database (uses same importer as Task 4)
                is_new = database.import_job(job_data)

                results["total_found"] += 1
                if is_new:
                    results["total_new"] += 1

        results["by_platform"][platform] = {
            "found": platform_found,
            "new": platform_new
        }

    return results
```

**Testing:**
```python
# Test ATS scanner
python -m src.scrapers.ats_scanner --platform greenhouse --title "AI Engineer" --limit 5
```

**Integration with Daily Workflow:**
```
Daily Workflow:
1. Generate Antigravity instructions (Task 3)
2. User runs Antigravity (~5 min)
3. Import Antigravity results (Task 4)
4. **Scan ATS platforms (Task 6)** ← NEW, automated
5. Process all with GLM (Task 5)
6. Generate campaign report (Task 7)
```

---

### ⏸️ Task 7: Campaign Report Generator

**Goal:** Generate Markdown daily campaign reports showing HIGH/MEDIUM match jobs.

**Implementation Plan:**

**File:** `src/output/report_generator.py`

```python
class CampaignReportGenerator:
    """
    Generates daily campaign reports with job matches.
    """

    async def generate_report(
        self,
        date: str = None  # Optional, defaults to today
    ) -> dict:
        """
        Generate campaign report for a specific date.

        Sections:
        1. HIGH MATCH JOBS (Tier 1, score ≥85)
        2. MEDIUM MATCH JOBS (Tier 2, 60≤score<85)
        3. Statistics & Cost
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        # Query database
        high_match = database.get_jobs_by_criteria(
            status='matched',
            decision_type='auto',
            date=date,
            order_by='ai_score DESC'
        )

        medium_match = database.get_jobs_by_criteria(
            status='matched',
            decision_type='manual',
            date=date,
            order_by='ai_score DESC'
        )

        # Generate Markdown
        markdown = self._generate_markdown(high_match, medium_match, date)

        # Save to campaigns/
        output_path = f"campaigns/campaign_{date}.md"
        with open(output_path, 'w') as f:
            f.write(markdown)

        return {
            "report_path": output_path,
            "high_match_count": len(high_match),
            "medium_match_count": len(medium_match)
        }

    def _generate_markdown(
        self,
        high_match: list,
        medium_match: list,
        date: str
    ) -> str:
        """Generate Markdown report."""

        md = f"""# Application Queue ({date})

## HIGH MATCH JOBS (Auto-Generated Resumes) ✓

| Status | Score | Company | Role | Resume | Apply |
|--------|-------|---------|------|--------|-------|
"""

        for job in high_match:
            resume_path = f"output/{job.company}_{job.title.replace(' ', '_')}.pdf"
            md += f"| [ ] | {job.ai_score} | {job.company} | {job.title} | [PDF]({resume_path}) | [Apply]({job.url}) |\n"

        md += f"""
→ **Ready to apply!** Resumes already customized for these jobs.

## MEDIUM MATCH JOBS (Need Your Decision) ⚠️

| Score | Company | Role | Why Medium? | Action |
|-------|---------|------|-------------|--------|
"""

        for job in medium_match:
            reasoning_short = job.ai_reasoning[:100] + "..."
            md += f"| {job.ai_score} | {job.company} | {job.title} | {reasoning_short} | [Approve] [Skip] |\n"

        # Statistics
        total_processed = database.count_jobs_by_date(date)
        total_cost = self._calculate_cost(high_match, medium_match)

        md += f"""
## Statistics

- **Total jobs processed:** {total_processed}
- **High match:** {len(high_match)} (resumes generated)
- **Medium match:** {len(medium_match)} (awaiting your review)
- **Cost today:** ${total_cost:.2f}

---

**Generated by Job Hunter AI** | {date}
"""

        return md
```

**MCP Tool:**

**File:** `src/mcp_server/tools/report.py`

```python
@server.tool()
async def generate_campaign_report(
    date: str = None  # Optional, defaults to today
) -> dict:
    """
    Generate daily campaign report.

    Returns:
        {
            "report_path": "campaigns/campaign_2026-01-29.md",
            "high_match_count": 8,
            "medium_match_count": 18,
            "total_cost_usd": 0.19,
            "message": "Report ready at campaigns/campaign_2026-01-29.md"
        }
    """
    generator = CampaignReportGenerator()
    result = await generator.generate_report(date)

    return {
        "report_path": result["report_path"],
        "high_match_count": result["high_match_count"],
        "medium_match_count": result["medium_match_count"],
        "message": f"Report ready at {result['report_path']}"
    }
```

**Example Output:**

**File:** `campaigns/campaign_2026-01-29.md`

```markdown
# Application Queue (2026-01-29)

## HIGH MATCH JOBS (Auto-Generated Resumes) ✓

| Status | Score | Company | Role | Resume | Apply |
|--------|-------|---------|------|--------|-------|
| [ ] | 92 | Scribd | AI Engineer | [PDF](output/Scribd_AI_Engineer.pdf) | [Apply](https://jobs.lever.co/scribd/...) |
| [ ] | 88 | Cohere | ML Engineer | [PDF](output/Cohere_ML_Engineer.pdf) | [Apply](https://jobs.lever.co/cohere/...) |
| [ ] | 86 | Anthropic | Research Engineer | [PDF](output/Anthropic_Research_Engineer.pdf) | [Apply](https://jobs.lever.co/anthropic/...) |

→ **Ready to apply!** Resumes already customized for these jobs.

## MEDIUM MATCH JOBS (Need Your Decision) ⚠️

| Score | Company | Role | Why Medium? | Action |
|-------|---------|------|-------------|--------|
| 78 | OpenAI | ML Ops Engineer | Contract role, but excellent skills match and learning opportunity... | [Approve] [Skip] |
| 75 | Hugging Face | AI Engineer | Remote in Europe timezone, may have scheduling challenges but great company... | [Approve] [Skip] |

## Statistics

- **Total jobs processed:** 120
- **High match:** 8 (resumes generated)
- **Medium match:** 18 (awaiting your review)
- **Cost today:** $0.19

---

**Generated by Job Hunter AI** | 2026-01-29
```

**Integration:**
```
Daily Workflow:
...
5. Process all with GLM (Task 5)
6. **Generate campaign report (Task 7)** ← NEW
7. User reviews report, approves medium matches
8. Generate application instructions (Task 8)
```

---

### ⏸️ Task 8: Application Instruction Generator

**Goal:** Generate JSON instructions for Antigravity to auto-apply to approved jobs.

**Implementation Plan:**

**File:** `src/agents/application_guide_generator.py`

```python
class ApplicationGuideGenerator:
    """
    Generates Antigravity application instructions for approved jobs.
    """

    async def generate_application_guide(
        self,
        campaign_date: str = None
    ) -> dict:
        """
        Generate application instructions for today's approved jobs.

        Workflow:
        1. Get all HIGH match jobs (decision_type='auto')
        2. Get approved MEDIUM match jobs (user_approved=True)
        3. For each job:
           - Generate form-filling instructions
           - Include resume path
           - Include cover letter (if needed)
        4. Save to instructions/apply_jobs_{date}.json
        """
        if not campaign_date:
            campaign_date = datetime.now().strftime('%Y-%m-%d')

        # Get jobs to apply
        high_match = database.get_jobs_by_criteria(
            status='matched',
            decision_type='auto',
            date=campaign_date
        )

        medium_approved = database.get_jobs_by_criteria(
            status='matched',
            decision_type='manual',
            user_approved=True,
            date=campaign_date
        )

        all_approved = high_match + medium_approved

        # Generate instructions for each
        applications = []
        for job in all_approved:
            app_instruction = {
                "job_id": job.id,
                "company": job.company,
                "title": job.title,
                "url": job.url,
                "resume_path": f"output/{job.company}_{job.title}.pdf",
                "instructions": self._generate_form_instructions(job),
                "pause_before_submit": True  # User final check
            }
            applications.append(app_instruction)

        # Create instruction file
        instruction_file = {
            "_metadata": {
                "generated_at": datetime.now().isoformat(),
                "task_type": "apply_to_jobs",
                "campaign_date": campaign_date,
                "version": "1.0"
            },
            "applications": applications,
            "rate_limit": {
                "max_applications_per_hour": 5,
                "delay_between_applications_seconds": 300
            }
        }

        output_path = f"instructions/apply_jobs_{campaign_date}.json"
        with open(output_path, 'w') as f:
            json.dump(instruction_file, f, indent=2)

        return {
            "instruction_file": output_path,
            "applications_count": len(applications),
            "high_match": len(high_match),
            "medium_approved": len(medium_approved)
        }

    def _generate_form_instructions(self, job) -> str:
        """
        Generate natural language instructions for form filling.

        Platform-specific based on URL:
        - Greenhouse: specific field names
        - Lever: specific field names
        - LinkedIn Easy Apply: click through
        """
        if 'greenhouse.io' in job.url:
            return f"""
            1. Navigate to {job.url}
            2. Click "Submit Application"
            3. Fill form:
               - First Name: [from resume]
               - Last Name: [from resume]
               - Email: [from credentials]
               - Phone: [from resume]
               - Resume: Upload {job.resume_path}
               - LinkedIn: [from credentials]
            4. Answer questions if any (use GLM for text responses)
            5. **PAUSE at Submit button for user review**
            """
        elif 'lever.co' in job.url:
            return f"""
            1. Navigate to {job.url}
            2. Click "Apply for this job"
            3. Fill form:
               - Full Name: [from resume]
               - Email: [from credentials]
               - Resume: Upload {job.resume_path}
               - Additional information: "See resume for details"
            4. **PAUSE at Submit button**
            """
        elif 'linkedin.com' in job.url and job.easy_apply:
            return f"""
            1. Navigate to {job.url}
            2. Click "Easy Apply"
            3. Step through wizard:
               - Upload resume: {job.resume_path}
               - Answer questions (use GLM for text)
               - Skip optional questions
            4. **PAUSE at Review/Submit page**
            """
        else:
            return f"""
            1. Navigate to {job.url}
            2. Look for "Apply" button
            3. Fill any form fields:
               - Name/Email: [from credentials]
               - Resume: Upload {job.resume_path}
            4. **PAUSE before final submit**
            """
```

**MCP Tool:**

**File:** `src/mcp_server/tools/application.py`

```python
@server.tool()
async def generate_application_instructions(
    campaign_date: str = None
) -> dict:
    """
    Generate application instructions for Antigravity.

    Returns:
        {
            "instruction_file": "instructions/apply_jobs_2026-01-29.json",
            "applications_count": 10,
            "high_match": 8,
            "medium_approved": 2,
            "message": "Please run: antigravity run {file}",
            "safety_note": "Antigravity will PAUSE before each submit"
        }
    """
    generator = ApplicationGuideGenerator()
    result = await generator.generate_application_guide(campaign_date)

    return {
        "instruction_file": result["instruction_file"],
        "applications_count": result["applications_count"],
        "message": f"Please run: antigravity run {result['instruction_file']}",
        "safety_note": "Antigravity will PAUSE before each submit for your review"
    }
```

**Example Output:**

**File:** `instructions/apply_jobs_2026-01-29.json`

```json
{
  "_metadata": {
    "generated_at": "2026-01-29T18:00:00",
    "task_type": "apply_to_jobs",
    "campaign_date": "2026-01-29",
    "version": "1.0"
  },
  "applications": [
    {
      "job_id": 123,
      "company": "Scribd",
      "title": "AI Engineer",
      "url": "https://jobs.lever.co/scribd/abc123",
      "resume_path": "output/Scribd_AI_Engineer.pdf",
      "instructions": "1. Navigate to...\n2. Click Apply...",
      "pause_before_submit": true
    }
  ],
  "rate_limit": {
    "max_applications_per_hour": 5,
    "delay_between_applications_seconds": 300
  }
}
```

**Safety Features:**
- **Pause before submit:** Antigravity stops at submit button for user final check
- **Rate limiting:** Max 5 applications per hour
- **Delay between applications:** 5 minutes to avoid detection
- **User approval:** Only applies to user-approved jobs

**Integration:**
```
Daily Workflow:
...
6. Generate campaign report (Task 7)
7. User reviews report, approves medium matches
8. **Generate application instructions (Task 8)** ← NEW
9. User runs Antigravity to auto-apply (~5 min)
10. Antigravity pauses before each submit for final check
```

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
cd W:/Code/job_viewer

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

### Implemented Tools (Phase 2)

| Tool | File | Purpose |
|------|------|---------|
| `generate_antigravity_scraping_guide` | `tools/antigravity.py` | Generate JSON for Antigravity scraping |
| `import_antigravity_results` | `tools/importer.py` | Import scraped JSON to database |
| `process_jobs_with_glm_tool` | `tools/gl_processor.py` | Filter jobs with GLM, three-tier routing |

### Planned Tools (Phase 3)

| Tool | File | Purpose |
|------|------|---------|
| `scan_ats_platforms` | `tools/ats_scanner.py` | Google dork ATS platforms (Task 6) |
| `generate_campaign_report` | `tools/report.py` | Generate daily campaign report (Task 7) |
| `generate_application_instructions` | `tools/application.py` | Generate Antigravity apply instructions (Task 8) |

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
- Check: Claude API key in .env

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

## Next Steps for Development

### Ready to Implement (Priority Order)

1. **Task 6:** ATS Dorking Scanner
   - File: `src/scrapers/ats_scanner.py`
   - Estimated: 300-400 lines
   - Complexity: Medium (Google dorking + HTML parsing)

2. **Task 7:** Campaign Report Generator
   - File: `src/output/report_generator.py`
   - Estimated: 200-300 lines
   - Complexity: Low (Markdown templating)

3. **Task 8:** Application Instruction Generator
   - File: `src/agents/application_guide_generator.py`
   - Estimated: 300-400 lines
   - Complexity: Medium (Platform-specific form templates)

### Development Best Practices

1. **Read this guide** before starting implementation
2. **Check ARCHITECTURE.md** for design decisions
3. **Follow code standards** (PEP 8, type hints, docstrings)
4. **Write unit tests** for new components
5. **Update this guide** after completing tasks
6. **Test manually** before marking complete

---

## References

- **README.md** - User guide and quick start
- **docs/ARCHITECTURE.md** - Architecture and design decisions
- **config/*.example.md** - Configuration templates

---

**Last Updated:** 2026-01-29
**Current Phase:** Phase 2 Complete (62.5%)
**Next Milestone:** Phase 3 (Tasks 6-8)

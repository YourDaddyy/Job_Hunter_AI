# Daily Job Hunt Skill

> **Orchestrate the daily job hunting workflow with AI-powered filtering and resume generation**

## Overview

This skill guides Claude through the complete daily job hunt workflow, from scraping jobs to generating application-ready resumes.

## When to Use

- User says: "Start job hunt", "Run daily job search", "Find jobs today"
- User invokes: `/job-hunt` command
- Daily/regular job hunting automation

## What This Skill Does

1. ✅ Generates Antigravity scraping instructions
2. ⏸️ Pauses for user to run Antigravity (manual, ~5 min)
3. ✅ Imports scraped data with deduplication
4. ✅ Filters jobs with AI (three-tier scoring)
5. ✅ Auto-generates resumes for high matches
6. ✅ Reports results to user

## Prerequisites

Before starting, verify:

```bash
# Check these files exist and are up-to-date:
- config/preferences.md     # Job titles, filters, salary requirements
- config/achievements.md    # Career highlights for AI matching
- config/credentials.md     # Platform login credentials
- config/resume.md          # Base resume for tailoring
- .env                      # API keys (GLM_API_KEY, ANTHROPIC_API_KEY)
```

**Quick check:** Read `config/preferences.md` to see if job titles and requirements are current.

## Workflow

### Step 1: Generate Antigravity Instructions

**Action:** Call MCP tool to generate scraping instructions

```
Tool: generate_antigravity_scraping_guide
Parameters: none (uses today's date)
```

**What it does:**
- Reads `config/preferences.md` (24 job titles)
- Reads `config/credentials.md` (login credentials)
- Generates `instructions/scrape_jobs_YYYY-MM-DD.json`

**Expected output:**
```json
{
  "instruction_file": "instructions/scrape_jobs_2026-01-29.json",
  "platforms": ["linkedin", "glassdoor", "wellfound", "indeed"],
  "job_titles": 24
}
```

**Tell user (copy-paste ready prompt for Antigravity):**

```
Scraping instructions generated!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COPY THIS TO ANTIGRAVITY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/turbo-all Run job search using W:\Code\job_viewer\instructions\scrape_jobs_2026-01-29.json

Log into LinkedIn, Indeed, Wellfound, Glassdoor and search for AI/ML/SDET roles (24 job titles). Filter for Remote/Canada. Save results to W:\Code\job_viewer\data\ as JSON files.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimated time: 5-10 minutes

Come back and say "done" when finished, or "skip" to use existing data.
```

### Step 2: Wait for User Confirmation

**PAUSE HERE - Manual task**

User will:
1. Run Antigravity command
2. Wait ~5 minutes for scraping
3. Respond "Done" or "Scraping complete"

**If user reports errors:**
- Check `config/credentials.md` for correct passwords
- Suggest manual login to clear CAPTCHAs
- Check if Antigravity is installed: `npm install -g antigravity-agent`

### Step 3: Import Scraped Data

**Action:** Call MCP tool to import JSON files

```
Tool: import_antigravity_results
Parameters: none (auto-scans data/*.json)
```

**What it does:**
- Scans `data/*.json` for new files
- Two-level deduplication:
  1. URL exact match
  2. Fuzzy match (company + title)
- Source priority handling (ATS > Visual platforms)

**Expected output:**
```json
{
  "total_jobs": 150,
  "new_jobs": 120,
  "url_duplicates": 15,
  "fuzzy_duplicates": 10,
  "updated_by_priority": 5,
  "stats_by_source": {
    "linkedin": {"total": 80, "new": 65},
    "glassdoor": {"total": 40, "new": 30},
    "wellfound": {"total": 20, "new": 15},
    "indeed": {"total": 10, "new": 10}
  }
}
```

**Tell user:**
```
Import complete!

- Total scraped: 150 jobs
- New unique jobs: 120
- Duplicates skipped: 30

Now filtering with AI...
```

**If no new jobs found:**
- Check if `data/*.json` files exist and have today's date
- Check if jobs are already in database (re-import won't duplicate)
- Suggest checking Antigravity output for errors

### Step 4: Process with AI (GLM)

**Action:** Call MCP tool to filter and score jobs

```
Tool: process_jobs_with_glm_tool
Parameters:
  force_reprocess: false (only process new jobs)
```

**What it does:**
- Reads `config/achievements.md` (your experience)
- Reads `config/preferences.md` (job criteria)
- For each unprocessed job:
  - GLM scores 0-100 based on match quality
  - Routes to three tiers:
    - ≥85: HIGH (auto-generate resume)
    - 60-84: MEDIUM (user review needed)
    - <60: LOW (auto-reject)

**Expected output:**
```json
{
  "total_processed": 120,
  "tier1_high_match": 8,
  "tier2_medium_match": 18,
  "tier3_low_match": 94,
  "resumes_generated": 8,
  "cost_usd": 0.19,
  "failed": 0
}
```

**Cost breakdown:**
- GLM filtering: ~$0.001 per job = $0.12 for 120 jobs
- Resume generation: ~$0.02 per resume = $0.16 for 8 resumes
- Total: ~$0.28

**Tell user:**
```
AI filtering complete!

Results:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 HIGH MATCH (Score ≥85): 8 jobs
   → Resumes auto-generated and saved to output/

⚠️  MEDIUM MATCH (Score 60-84): 18 jobs
   → Require your review and approval

❌ LOW MATCH (Score <60): 94 jobs
   → Auto-rejected (not a good fit)

Cost today: $0.19
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

High match jobs with resumes ready:
1. Scribd - AI Engineer (Score: 92)
   Resume: output/Scribd_AI_Engineer.pdf
   Apply: https://jobs.lever.co/scribd/...

2. Cohere - ML Engineer (Score: 88)
   Resume: output/Cohere_ML_Engineer.pdf
   Apply: https://jobs.lever.co/cohere/...

... (show all 8)

Medium match jobs (need your decision):
1. OpenAI - ML Ops Engineer (Score: 78)
   Reason: Contract role, but excellent skills match

2. Hugging Face - AI Engineer (Score: 75)
   Reason: Europe timezone, but great company

... (show all 18)

Next steps:
1. Review high match jobs and apply directly
2. Review medium match jobs - approve ones you want
3. Run campaign report generator (coming soon - Task 7)
```

**If processing fails:**
- Check GLM_API_KEY in `.env`
- Check API quota at https://open.bigmodel.cn/
- Check `config/achievements.md` and `config/preferences.md` exist
- Try with smaller batch: Set limit in gl_processor.py

### Step 5: Summary and Next Steps

**Tell user:**
```
✅ Daily job hunt complete!

Summary:
- Scraped: 150 jobs from 4 platforms
- Imported: 120 new unique jobs
- High match: 8 (resumes ready in output/)
- Medium match: 18 (awaiting your review)
- Cost: $0.19

Your action items:
1. Review high match jobs (already have tailored resumes)
2. Apply to jobs you like
3. Review medium match jobs in database
4. Approve/skip medium matches for next round

Next run: Tomorrow (recommended daily)
```

## Error Handling

### Common Issues

**1. "No instruction file generated"**
```
Troubleshooting:
- Check config/preferences.md exists
- Check config/credentials.md exists
- Check file syntax (should be valid Markdown with YAML frontmatter)
```

**2. "Antigravity scraping failed"**
```
Troubleshooting:
- Check credentials in config/credentials.md
- Try manual login to clear CAPTCHAs
- Check if account is locked
- Verify Antigravity is installed: npm list -g antigravity-agent
```

**3. "No new jobs imported"**
```
Troubleshooting:
- Check data/*.json files exist with today's date
- Verify JSON format is valid
- Jobs may already be in database (re-imports are safe but won't duplicate)
```

**4. "GLM API error: rate limit"**
```
Troubleshooting:
- Wait 60 seconds and retry
- Check API quota at https://open.bigmodel.cn/
- Reduce batch size if needed
```

**5. "Resume generation failed"**
```
Troubleshooting:
- Check ANTHROPIC_API_KEY in .env
- Check config/resume.md exists
- Check config/achievements.md exists
- Verify Claude API quota
```

### Recovery Steps

If workflow interrupted:

**After Step 1 (instructions generated):**
- Just run Antigravity with the generated file
- Continue from Step 2

**After Step 2 (Antigravity done):**
- Call `import_antigravity_results` tool
- Continue from Step 3

**After Step 3 (import done):**
- Call `process_jobs_with_glm_tool` with `force_reprocess: false`
- Only processes new jobs

**After Step 4 (processing done):**
- Results are saved in database
- Query database for matched jobs anytime

## Database Queries

If user wants to see results later:

```python
# Get high match jobs (resumes already generated)
SELECT id, company, title, ai_score, url
FROM jobs
WHERE status='matched' AND decision_type='auto'
ORDER BY ai_score DESC;

# Get medium match jobs (need review)
SELECT id, company, title, ai_score, ai_reasoning
FROM jobs
WHERE status='matched' AND decision_type='manual'
ORDER BY ai_score DESC;

# Get today's statistics
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN status='matched' THEN 1 ELSE 0 END) as matched,
  SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected
FROM jobs
WHERE DATE(created_at) = DATE('now');
```

## Configuration Tips

### Optimizing Job Titles (config/preferences.md)

**Current: 24 job titles**

Tips:
- Keep titles specific (not just "Engineer")
- Include variations: "AI Engineer", "Machine Learning Engineer", "Applied AI Engineer"
- Update seasonally based on market trends
- Remove titles that consistently return poor matches

### Improving Match Quality

**If too many low matches (<60):**
- Make preferences.md more specific
- Add more detail to achievements.md
- Increase minimum salary to filter out junior roles
- Add more red flags (e.g., "no visa sponsorship")

**If too few high matches (≥85):**
- Broaden job titles in preferences.md
- Reduce salary requirements temporarily
- Check if achievements.md highlights relevant skills
- Consider lowering HIGH threshold to 80 (in gl_processor.py)

## Advanced Usage

### Force Re-process All Jobs

If you updated achievements.md or preferences.md:

```
Tool: process_jobs_with_glm_tool
Parameters:
  force_reprocess: true
```

This re-scores ALL jobs in database with new criteria.

**Warning:** This costs ~$0.001 per job. If you have 500 jobs in database, cost = $0.50

### Manual Import Specific Files

If you only want to import specific platforms:

```
Tool: import_antigravity_results
Parameters:
  files: ["data/linkedin_2026-01-29.json", "data/glassdoor_2026-01-29.json"]
```

## Cost Management

### Daily Costs

Typical daily job hunt:
- Scraping: Free (Antigravity uses your accounts)
- Import: Free (local database)
- GLM filtering: $0.12 (120 jobs × $0.001)
- Resume generation: $0.16 (8 resumes × $0.02)
- **Total: ~$0.28/day or ~$8.40/month**

### Cost Optimization

**Reduce GLM costs:**
- Set lower `limit` when generating instructions (scrape fewer jobs)
- Filter platforms: Only scrape LinkedIn + ATS platforms
- Run every other day instead of daily

**Reduce resume costs:**
- Increase HIGH threshold to 90 (fewer auto-resumes)
- Only generate resumes for MEDIUM matches you approve
- Use cheaper model for resume generation (set in gl_processor.py)

## Files Reference

### Input Files (You Edit)

| File | Purpose | Update Frequency |
|------|---------|-----------------|
| `config/preferences.md` | Job titles, salary, location | Weekly/Monthly |
| `config/achievements.md` | Career highlights | When you complete projects |
| `config/credentials.md` | Platform logins | When passwords change |
| `config/resume.md` | Base resume content | Monthly |
| `.env` | API keys | Once (setup) |

### Output Files (Generated)

| File | Purpose | Lifetime |
|------|---------|----------|
| `instructions/scrape_jobs_*.json` | Antigravity scraping guide | Daily (1 per day) |
| `data/*.json` | Scraped job data | Temporary (imported then can delete) |
| `output/*.pdf` | Tailored resumes | Permanent (for applications) |
| `data/jobs.db` | Job database | Permanent (grows over time) |

### Documentation Files (Read for Help)

| File | For | When to Read |
|------|-----|--------------|
| `README.md` | Users, main agents | First time setup |
| `docs/ARCHITECTURE.md` | Understanding design | Troubleshooting |
| `docs/DEVELOPMENT_GUIDE.md` | Developers, sub-agents | Implementing features |

## Task Status

### ✅ All Features Implemented (100% Complete)

- Task 1-2: Database + Cleanup ✅
- Task 3: Antigravity instruction generator ✅
- Task 4: JSON importer with deduplication ✅
- Task 5: GLM processor with three-tier scoring ✅
- Task 6: ATS platform scanner (Greenhouse/Lever/Ashby/Workable) ✅
- Task 7: Campaign report generator (Markdown daily reports) ✅
- Task 8: Application instruction generator (auto-apply with Antigravity) ✅

**All features working - system is production-ready!**

## Quick Reference

### Daily Workflow Commands

```bash
# 1. Generate instructions
# (Claude calls generate_antigravity_scraping_guide)

# 2. Run Antigravity (you run this manually)
antigravity run instructions/scrape_jobs_2026-01-29.json

# 3. Import + Process (Claude calls these)
# import_antigravity_results
# process_jobs_with_glm_tool

# 4. Review results
ls output/  # See generated resumes
```

### Useful Database Commands

```bash
# Open database
sqlite3 data/jobs.db

# See today's high matches
SELECT company, title, ai_score FROM jobs
WHERE status='matched' AND decision_type='auto'
AND DATE(created_at) = DATE('now');

# Count jobs by status
SELECT status, COUNT(*) FROM jobs GROUP BY status;

# Exit
.exit
```

## Support

### If This Skill Fails

1. **Read error messages carefully** - they usually indicate the problem
2. **Check Prerequisites** - verify all config files exist
3. **Check API keys** - ensure GLM_API_KEY and ANTHROPIC_API_KEY in .env
4. **Check database** - ensure data/jobs.db exists (run `python -m src.core.database init`)
5. **Read troubleshooting** - see docs/DEVELOPMENT_GUIDE.md

### Getting Help

```bash
# Check logs
tail -f logs/job_hunter.log

# Test MCP tools directly
python -m src.mcp_server.server

# Test components individually
python -m src.agents.instruction_generator
python -m src.core.importer data/test.json
python -m src.core.gl_processor --limit 5
```

## Success Metrics

After a successful daily job hunt, you should see:

✅ **Instruction file generated** in `instructions/`
✅ **4 JSON files scraped** in `data/` (linkedin, glassdoor, wellfound, indeed)
✅ **100+ jobs imported** to database (varies by day)
✅ **5-15 high matches** with resumes in `output/`
✅ **10-30 medium matches** for review
✅ **Total cost: $0.20-0.30** per day

**Quality indicators:**
- High matches (≥85) are actually jobs you'd apply to (90%+ accuracy)
- Medium matches (60-84) are worth reviewing (70%+ useful)
- Low matches (<60) are correctly rejected (95%+ accuracy)

If quality is off, update `config/preferences.md` and `config/achievements.md` to improve AI matching.

---

**Skill Version:** 2.0
**Last Updated:** 2026-01-30
**Workflow Status:** 100% Complete - All Features Working
**Estimated Time:** 15 minutes (5 min manual Antigravity + 10 min AI processing)
**Cost Per Run:** ~$0.20-0.30

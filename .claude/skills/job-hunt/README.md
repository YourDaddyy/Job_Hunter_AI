# Job Hunt Skill

This skill orchestrates the daily job hunting workflow with AI-powered filtering and resume generation.

**Agent Guide:** Claude auto-reads `CLAUDE.md` in project root for workflow details.

## Quick Commands

| Command | What It Does |
|---------|--------------|
| `start job hunt` | Full workflow (scrape + filter + report) |
| `/job-hunt` | Same as above |
| `run ATS scanner` | Quick scan (no browser, Google dorking only) |
| `reprocess jobs` | Re-filter existing jobs with updated preferences |
| `show job stats` | Database summary |
| `find high match jobs` | List jobs with score >= 85 |

## How to Use

### Full Workflow (with Antigravity)
```bash
> start job hunt
# Follow prompts to run Antigravity
```

### Quick Mode (No Browser Needed)
```bash
> run ATS scanner only
# Scans Greenhouse, Lever, Ashby, Workable via Google
```

### Reprocess Mode (Existing Jobs)
```bash
> reprocess unscored jobs
# Re-filters jobs after updating preferences.md
```

## What This Skill Does

1. ✅ Generates Antigravity scraping instructions
2. ⏸️ Pauses for you to run Antigravity (~5 min)
3. ✅ Imports scraped data with smart deduplication
4. ✅ Filters jobs with AI (0-100 scoring)
5. ✅ Auto-generates resumes for high matches (≥85)
6. ✅ Reports results with actionable next steps

## Quick Start

**First time setup:**

1. Copy config templates:
   ```bash
   cp config/preferences.example.md config/preferences.md
   cp config/achievements.example.md config/achievements.md
   cp config/credentials.example.md config/credentials.md
   cp config/resume.example.md config/resume.md
   ```

2. Edit config files with your information

3. Set API keys in `.env`:
   ```bash
   GLM_API_KEY=your_key_here
   ANTHROPIC_API_KEY=your_key_here
   ```

4. Initialize database:
   ```bash
   python -m src.core.database init
   ```

**Daily usage:**

1. Start Claude Code in this directory
2. Run: `/job-hunt` or say "Start job hunt"
3. Follow Claude's instructions (run Antigravity when prompted)
4. Review results and apply to jobs

## Workflow

```
You: "Start job hunt"
  ↓
Claude: Generates instructions/scrape_jobs_2026-01-29.json
Claude: "Please run: antigravity run instructions/..."
  ↓
You: [Run Antigravity command] (~5 minutes)
  ↓
You: "Done scraping"
  ↓
Claude: Imports data/*.json → database
Claude: Filters 120 jobs with AI
Claude: Generates 8 resumes for high matches
  ↓
Claude: "Results ready! 8 high matches, 18 medium matches"
  ↓
You: Review and apply to jobs
```

**Time:** ~15 minutes (5 min manual + 10 min automated)
**Cost:** ~$0.20-0.30 per day

## Expected Results

After running the skill:

- **High Match Jobs (≥85 score):** 5-15 jobs
  - Resumes auto-generated in `output/`
  - Ready to apply immediately

- **Medium Match Jobs (60-84 score):** 10-30 jobs
  - Require your review and approval
  - Can generate resumes on demand

- **Low Match Jobs (<60 score):** 70-100 jobs
  - Auto-rejected, stored for reference

## Configuration

The skill reads these files (you should edit them):

| File | What to Put | Update Frequency |
|------|-------------|-----------------|
| `config/preferences.md` | Job titles, salary, location | Weekly |
| `config/achievements.md` | Career highlights | When you finish projects |
| `config/credentials.md` | LinkedIn/Indeed/etc logins | When passwords change |
| `config/resume.md` | Your resume content | Monthly |

## Troubleshooting

**"No jobs found"**
- Check if Antigravity actually scraped files to `data/*.json`
- Check if credentials are correct in `config/credentials.md`

**"GLM API error"**
- Verify `GLM_API_KEY` in `.env`
- Check quota at https://open.bigmodel.cn/

**"Resume generation failed"**
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check `config/resume.md` and `config/achievements.md` exist

**"Antigravity command not found"**
- Install: `npm install -g antigravity-agent`

## Cost Breakdown

Per daily run:
- Antigravity scraping: **Free** (uses your accounts)
- GLM filtering (120 jobs): **$0.12** (~$0.001/job)
- Resume generation (8 resumes): **$0.16** (~$0.02/resume)
- **Total: ~$0.28/day** or **~$8/month**

Compare to:
- LinkedIn Premium: $30-100/month
- Your time manually searching: 10+ hours/week (priceless)

## What's Next

After this skill runs, you'll have:
- ✅ Tailored PDF resumes in `output/` folder
- ✅ List of high-match jobs to apply to
- ✅ List of medium-match jobs for review
- ✅ All job data in SQLite database

**All features implemented:**
- 📊 Daily campaign reports (Markdown tables) - `campaigns/`
- 🔍 ATS platform scanner (automated Greenhouse/Lever/Ashby/Workable)
- 🤖 Auto-apply instructions (Antigravity form filling)

## Support

- **Skill documentation:** See `SKILL.md` for detailed workflow
- **Project documentation:** See `../../../README.md` for overview
- **Technical details:** See `../../../docs/DEVELOPMENT_GUIDE.md`

## Skill Status

**100% Complete - All Features Implemented**

- Phase 1: Database + Infrastructure ✅
- Phase 2: Core workflow (Tasks 3-5) ✅
- Phase 3: ATS Scanner (Task 6) ✅
- Phase 4: Campaign Reports (Task 7) ✅
- Phase 5: Application Generator (Task 8) ✅

---

**Version:** 2.0
**Last Updated:** 2026-01-30
**Estimated Time:** 15 minutes per run
**Cost:** ~$0.20-0.30 per run

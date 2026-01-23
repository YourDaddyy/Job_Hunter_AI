# Job Hunter - AI-Powered Autonomous Job Search System

An intelligent job hunting assistant that uses Claude Code CLI as the main orchestrator with MCP Server tools to automate job searching, filtering, and application.

## Features

- **Multi-platform scraping**: LinkedIn, Indeed, Wellfound
- **Smart filtering**: Uses GLM (cheap) for high-throughput screening
- **Intelligent decisions**: Auto-apply for high matches, ask user for medium matches
- **Resume tailoring**: Claude customizes your resume for each job
- **Deduplication**: Prevents applying to the same job twice
- **Telegram notifications**: Get updates and make decisions on the go

## Architecture

```
Claude Code CLI (Orchestrator)
        │
        ▼
   MCP Server (job-hunter)
        │
        ├── Scraper (Playwright)
        ├── Filter (GLM API)
        ├── Tailor (Claude API)
        ├── Applier (Playwright)
        └── Notifier (Telegram)
        │
        ▼
    SQLite Database
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd job_viewer
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your API keys
```

### 3. Configure Personal Information

Copy the example config files and fill in your information:

```bash
# Copy templates
cp config/resume.example.md config/resume.md
cp config/preferences.example.md config/preferences.md
cp config/achievements.example.md config/achievements.md

# Edit each file with your personal information
```

**Important**: The actual config files (`resume.md`, `preferences.md`, `achievements.md`) are gitignored to protect your privacy.

### 4. Initialize Database

```bash
python -m src.core.database init
```

### 5. Run with Claude Code

```bash
claude

# Then in Claude Code:
> /job-hunt
# or
> Start job hunting
```

## Configuration Files

| File | Purpose | Committed to Git? |
|------|---------|-------------------|
| `.env.example` | Environment template | Yes |
| `.env` | Your actual secrets | No |
| `config/*.example.md` | Config templates | Yes |
| `config/resume.md` | Your resume | No |
| `config/preferences.md` | Your job preferences | No |
| `config/achievements.md` | Your achievements | No |

## Decision Thresholds

| Match Score | Action |
|-------------|--------|
| >= 85% | Auto-apply |
| 60% - 85% | Ask via Telegram |
| < 60% | Auto-reject |

These thresholds are configurable in `config/preferences.md`.

## Tech Stack

- **Orchestrator**: Claude Code CLI
- **Tools Interface**: MCP Server (Python)
- **Filtering LLM**: GLM API (cost-effective)
- **Decision LLM**: Claude API (high quality)
- **Browser Automation**: Playwright
- **Database**: SQLite
- **Notifications**: Telegram Bot

## Project Structure

```
job_viewer/
├── src/
│   ├── mcp_server/          # MCP Server & Tools
│   ├── core/                # Business Logic
│   └── utils/               # Utilities
├── config/                  # Configuration (templates + personal)
├── data/                    # SQLite DB & generated files
├── templates/               # Resume HTML templates
└── .claude/skills/          # Claude Code skills
```

## License

MIT

## Disclaimer

This tool is for personal use and educational purposes. Automated access to job platforms may violate their Terms of Service. Users are responsible for compliance with platform rules.

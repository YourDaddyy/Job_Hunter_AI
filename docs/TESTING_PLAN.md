# Job Hunter - Testing & Setup Plan

This document provides a comprehensive testing plan for setting up and verifying all components of the Job Hunter system.

---

## Table of Contents

1. [Pre-Setup: Browser Sessions](#1-pre-setup-browser-sessions)
2. [Component Testing](#2-component-testing)
3. [Known Issues & Solutions](#3-known-issues--solutions)
4. [Testing Checklist](#4-testing-checklist)

---

## 1. Pre-Setup: Browser Sessions

### Overview

Yes, you CAN pre-set up browser sessions manually and let the project reuse them. The system uses Playwright's session persistence to save cookies, localStorage, and other browser state.

### Session Storage Location

```
data/sessions/
├── linkedin_session.json
├── indeed_session.json
├── wellfound_session.json
└── glassdoor_session.json
```

### Manual Session Setup Workflow

For each platform, you can manually log in once and save the session:

#### Step 1: Create Session Setup Script

```python
# scripts/setup_session.py
import asyncio
from playwright.async_api import async_playwright

async def setup_session(platform: str):
    """Manually log in and save session for a platform."""

    urls = {
        "linkedin": "https://www.linkedin.com/login",
        "indeed": "https://secure.indeed.com/account/login",
        "wellfound": "https://wellfound.com/login",
        "glassdoor": "https://www.glassdoor.com/profile/login_input.htm"
    }

    async with async_playwright() as p:
        # Launch visible browser for manual login
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()
        await page.goto(urls[platform])

        print(f"\n{'='*50}")
        print(f"Manual Login Required for {platform.upper()}")
        print(f"{'='*50}")
        print("1. Log in manually in the browser window")
        print("2. Complete any 2FA if required")
        print("3. Navigate to ensure you're fully logged in")
        print("4. Press ENTER here when done...")
        input()

        # Save session
        session_path = f"data/sessions/{platform}_session.json"
        storage = await context.storage_state(path=session_path)

        print(f"Session saved to: {session_path}")
        await browser.close()

if __name__ == "__main__":
    import sys
    platform = sys.argv[1] if len(sys.argv) > 1 else "linkedin"
    asyncio.run(setup_session(platform))
```

#### Step 2: Run for Each Platform

```bash
# Set up LinkedIn session
python scripts/setup_session.py linkedin

# Set up Indeed session (use Google OAuth in browser)
python scripts/setup_session.py indeed

# Set up Wellfound session
python scripts/setup_session.py wellfound
```

#### Step 3: Verify Session Files Exist

```bash
ls -la data/sessions/
# Should show:
# linkedin_session.json
# indeed_session.json
# wellfound_session.json
```

### Session Reuse in Scrapers

The scrapers automatically load saved sessions:

```python
# In each scraper's login() method:
session_path = f"data/sessions/{platform}_session.json"
if os.path.exists(session_path):
    context = await browser.new_context(storage_state=session_path)
    # Already logged in, skip login flow
```

---

## 2. Component Testing

### 2.1 Configuration Parser

**File:** `src/utils/markdown_parser.py`

**Test Commands:**
```python
# Test in Python REPL
from src.utils.markdown_parser import MarkdownParser

# Test credentials parsing
parser = MarkdownParser()
creds = parser.parse_credentials("config/credentials.md")
print(f"LinkedIn email: {creds.get('linkedin', {}).get('email')}")

# Test preferences parsing
prefs = parser.parse_preferences("config/preferences.md")
print(f"Target positions: {prefs.target_positions}")
print(f"Location prefs: {prefs.locations}")

# Test achievements parsing
achievements = parser.parse_achievements("config/achievements.md")
print(f"Number of achievements: {len(achievements)}")

# Test resume parsing
resume = parser.parse_resume("config/resume.md")
print(f"Name: {resume.personal_info.name}")
print(f"Title: {resume.personal_info.title}")
```

**Expected Results:**
- Credentials: Should return dict with platform keys (linkedin, indeed, wellfound, glm)
- Preferences: Should return object with target_positions (16 items), locations, salary range
- Achievements: Should return list of 8+ achievement entries
- Resume: Should return Resume object with personal_info, summary_bullets, experience, skills, projects, education

### 2.2 Database Module

**File:** `src/core/database.py`

**Test Commands:**
```python
from src.core.database import Database

db = Database("data/test_jobs.db")

# Test job insertion
job_data = {
    "platform": "linkedin",
    "external_id": "test123",
    "title": "AI Engineer",
    "company": "Test Corp",
    "location": "Remote",
    "url": "https://example.com/job/123",
    "description": "Test job description",
    "posted_date": "2024-01-15"
}
db.insert_job(job_data)

# Test job retrieval
jobs = db.get_jobs(platform="linkedin")
print(f"Jobs found: {len(jobs)}")

# Test duplicate handling
db.insert_job(job_data)  # Should not create duplicate

# Cleanup
import os
os.remove("data/test_jobs.db")
```

### 2.3 Browser Manager

**File:** `src/scrapers/browser_manager.py`

**Test Commands:**
```python
import asyncio
from src.scrapers.browser_manager import BrowserManager

async def test_browser():
    browser = BrowserManager(headless=False)
    await browser.launch()

    page = await browser.new_page()
    await page.goto("https://www.google.com")

    title = await page.title()
    print(f"Page title: {title}")

    await browser.close()

asyncio.run(test_browser())
```

**Expected:** Browser opens, navigates to Google, prints title, closes cleanly.

### 2.4 LinkedIn Scraper

**File:** `src/scrapers/linkedin.py`

**Pre-requisite:** LinkedIn session must be set up (see Section 1)

**Test Commands:**
```python
import asyncio
from src.scrapers.linkedin import LinkedInScraper

async def test_linkedin():
    scraper = LinkedInScraper(headless=False)

    # Test with saved session
    await scraper.initialize()

    # Check if logged in
    is_logged_in = await scraper.check_login_status()
    print(f"Logged in: {is_logged_in}")

    if is_logged_in:
        # Test job search
        jobs = await scraper.search_jobs(
            keywords="AI Engineer",
            location="Remote",
            limit=5
        )
        print(f"Jobs found: {len(jobs)}")
        for job in jobs:
            print(f"  - {job['title']} at {job['company']}")

    await scraper.close()

asyncio.run(test_linkedin())
```

**Known Issue:** May get HTTP 451 error if IP is blocked. See Section 3.

### 2.5 Indeed Scraper

**File:** `src/scrapers/indeed.py`

**Note:** Indeed uses Google OAuth. Must set up session manually.

**Test Commands:**
```python
import asyncio
from src.scrapers.indeed import IndeedScraper

async def test_indeed():
    scraper = IndeedScraper(headless=False)
    await scraper.initialize()

    # Test job search (may work without login for basic search)
    jobs = await scraper.search_jobs(
        keywords="Software Engineer",
        location="Remote",
        limit=5
    )
    print(f"Jobs found: {len(jobs)}")

    await scraper.close()

asyncio.run(test_indeed())
```

### 2.6 Wellfound Scraper

**File:** `src/scrapers/wellfound.py`

**Test Commands:**
```python
import asyncio
from src.scrapers.wellfound import WellfoundScraper

async def test_wellfound():
    scraper = WellfoundScraper(headless=False)
    await scraper.initialize()

    # Attempt login with credentials
    from src.utils.markdown_parser import MarkdownParser
    parser = MarkdownParser()
    creds = parser.parse_credentials("config/credentials.md")

    wellfound_creds = creds.get("wellfound", {})
    if wellfound_creds:
        success = await scraper.login(
            wellfound_creds["email"],
            wellfound_creds["password"]
        )
        print(f"Login success: {success}")

    await scraper.close()

asyncio.run(test_wellfound())
```

### 2.7 Resume Tailor

**File:** `src/core/tailor.py`

**Test Commands:**
```python
from src.core.tailor import ResumeTailor
from src.utils.markdown_parser import MarkdownParser

parser = MarkdownParser()
resume = parser.parse_resume("config/resume.md")
achievements = parser.parse_achievements("config/achievements.md")

tailor = ResumeTailor(resume, achievements)

# Test resume data building (no API call)
job_description = """
AI Engineer - Remote
Requirements:
- Python, PyTorch
- LLM experience
- RAG systems
"""

# Build context for tailoring
context = tailor._build_resume_data()
print(f"Resume sections: {list(context.keys())}")
```

### 2.8 PDF Generation

**Test Commands:**
```python
from src.core.tailor import ResumeTailor
from src.utils.markdown_parser import MarkdownParser

parser = MarkdownParser()
resume = parser.parse_resume("config/resume.md")

tailor = ResumeTailor(resume, [])

# Generate PDF without tailoring (base resume)
output_path = "data/resumes/test_resume.pdf"
tailor.generate_pdf(output_path, template="professional")
print(f"PDF generated: {output_path}")
```

**Expected:** PDF file created matching the Word document format.

---

## 3. Known Issues & Solutions

### 3.1 LinkedIn HTTP 451 Error

**Symptom:** Job search returns "HTTP ERROR 451" or Chinese error page "该网页无法正常运�?

**Cause:** LinkedIn blocks access from certain IPs/regions, especially cloud servers or VPNs.

**Solutions:**
1. **Use residential IP:** Run from home network, not cloud server
2. **Use proxy:** Configure proxy in `config/credentials.md`:
   ```yaml
   service: proxy
   url: http://user:pass@residential-proxy:port
   enabled: true
   ```
3. **Use VPN:** Connect to US/Canada VPN before running
4. **Manual session:** Log in manually from allowed IP, save session, copy to server

### 3.2 Indeed Google OAuth

**Symptom:** Cannot automate Indeed login because it uses Google OAuth popup.

**Solution:** Manual session setup only.
1. Run `python scripts/setup_session.py indeed`
2. Click "Sign in with Google" in browser
3. Complete Google login manually
4. Session will be saved for reuse

### 3.3 CAPTCHA Challenges

**Symptom:** Login fails with CAPTCHA required.

**Solutions:**
1. **Slow down:** Add delays between actions
2. **Human-like behavior:** Add random mouse movements
3. **Manual intervention:** Use non-headless mode, solve manually
4. **Anti-detect browser:** Use undetected-chromedriver or similar

### 3.4 Session Expiry

**Symptom:** Saved session no longer works.

**Cause:** Sessions expire (LinkedIn ~30 days, others vary).

**Solution:** Re-run session setup script periodically.

---

## 4. Testing Checklist

### Initial Setup

- [ ] Python 3.10+ installed
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Playwright browsers installed: `playwright install chromium`
- [ ] Config files exist:
  - [ ] `config/credentials.md` (with real credentials)
  - [ ] `config/preferences.md`
  - [ ] `config/achievements.md`
  - [ ] `config/resume.md`
- [ ] Data directories exist:
  - [ ] `data/sessions/`
  - [ ] `data/resumes/`
  - [ ] `data/logs/`

### Session Setup

- [ ] LinkedIn session saved (`data/sessions/linkedin_session.json`)
- [ ] Indeed session saved (`data/sessions/indeed_session.json`)
- [ ] Wellfound session saved (`data/sessions/wellfound_session.json`)

### Component Tests

- [ ] Configuration parser reads all config files correctly
- [ ] Database module creates DB and inserts/retrieves jobs
- [ ] Browser manager launches and closes cleanly
- [ ] LinkedIn scraper loads session and checks login status
- [ ] Indeed scraper can search jobs
- [ ] Wellfound scraper can log in
- [ ] Resume tailor generates PDF correctly

### Integration Tests

- [ ] Full scrape cycle: login �?search �?parse �?save to DB
- [ ] Job filtering: new jobs scored against preferences
- [ ] Notification: jobs meeting threshold trigger alert
- [ ] Resume tailoring: job description �?tailored resume PDF

---

## 5. Quick Start Commands

```bash
# 1. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 2. Set up sessions (run each, log in manually)
python scripts/setup_session.py linkedin
python scripts/setup_session.py indeed
python scripts/setup_session.py wellfound

# 3. Test configuration
python -c "from src.utils.markdown_parser import MarkdownParser; p = MarkdownParser(); print(p.parse_preferences('config/preferences.md'))"

# 4. Test database
python -c "from src.core.database import Database; db = Database('data/jobs.db'); print('DB OK')"

# 5. Test PDF generation
python -c "
from src.core.tailor import ResumeTailor
from src.utils.markdown_parser import MarkdownParser
p = MarkdownParser()
r = p.parse_resume('config/resume.md')
t = ResumeTailor(r, [])
t.generate_pdf('data/resumes/test.pdf', 'professional')
print('PDF generated')
"
```

---

## 6. Agent Instructions

For AI agents continuing this work:

1. **Read this document first** to understand the system state
2. **Check session files** - if missing, guide user through manual setup
3. **Test components individually** before running full pipeline
4. **Handle HTTP 451** by suggesting proxy/VPN solutions
5. **Don't automate Indeed OAuth** - always use manual session setup
6. **Save sessions after successful login** for future reuse

### Key Files Reference

| Component | File Path |
|-----------|-----------|
| Config Parser | `src/utils/markdown_parser.py` |
| Database | `src/core/database.py` |
| Browser Manager | `src/scrapers/browser_manager.py` |
| Base Scraper | `src/scrapers/base.py` |
| LinkedIn Scraper | `src/scrapers/linkedin.py` |
| Indeed Scraper | `src/scrapers/indeed.py` |
| Wellfound Scraper | `src/scrapers/wellfound.py` |
| Resume Tailor | `src/core/tailor.py` |
| HTML Template | `templates/resume/professional.html` |

### BrowserManager API

```python
# Correct usage (not start/stop)
browser = BrowserManager(headless=False)
await browser.launch()      # NOT .start()
page = await browser.new_page()
await browser.close()       # NOT .stop()
```

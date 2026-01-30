# ATS Scrapers

This directory contains scrapers for Applicant Tracking System (ATS) platforms.

## ATS Dorking Scanner

**File:** `ats_scanner.py`
**Status:** ✅ Fully Implemented (Task 6)

### Overview

Automated Google dorking scanner that discovers job postings from major ATS platforms without requiring browser automation. This scanner provides the highest quality job listings (priority 1) as they come directly from company career pages.

### Supported Platforms

| Platform | Domain | URL Pattern | Priority |
|----------|--------|-------------|----------|
| **Greenhouse** | jobs.greenhouse.io | `https://boards.greenhouse.io/{company}/jobs/{id}` | 1 |
| **Lever** | jobs.lever.co | `https://jobs.lever.co/{company}/{id}` | 1 |
| **Ashby** | jobs.ashbyhq.com | `https://jobs.ashbyhq.com/{company}/{id}` | 1 |
| **Workable** | apply.workable.com | `https://apply.workable.com/{company}/j/{id}` | 1 |

### Features

- **Google Dorking:** Automated search query generation for each platform
- **HTML Parsing:** BeautifulSoup-based extraction with multiple selector fallbacks
- **Deduplication:** Integrates with existing fuzzy hash system
- **Priority Routing:** ATS jobs automatically get highest priority (1)
- **Rate Limiting:** Configurable delays to avoid blocking (default: 1s)
- **Zero Cost:** No paid APIs required

### Usage

#### CLI Test Mode
```bash
# Test single platform
python -m src.scrapers.ats_scanner lever "AI Engineer" 5

# Arguments:
#   platform: greenhouse|lever|ashby|workable
#   title: Job title to search for
#   limit: Maximum results to fetch
```

#### MCP Tool
```python
from src.mcp_server.tools.ats_scanner import scan_ats_platforms_tool

# Scan all platforms with default settings
result = await scan_ats_platforms_tool()

# Custom scan
result = await scan_ats_platforms_tool(
    job_titles=["AI Engineer", "ML Engineer"],
    max_results_per_platform=50,
    location="Remote"
)
```

#### Programmatic Usage
```python
from src.scrapers.ats_scanner import ATSScanner

scanner = ATSScanner()

# Scan all platforms
result = await scanner.scan_all_platforms(
    job_titles=["AI Engineer"],
    max_results_per_platform=50,
    location="Remote"
)

# Scan single platform
result = await scanner.scan_platform(
    platform="lever",
    job_titles=["AI Engineer"],
    max_results=50
)
```

### Example Queries

The scanner generates Google dork queries like:

```
site:jobs.greenhouse.io "AI Engineer" "Remote" -expired -closed
site:jobs.lever.co "ML Engineer" "Canada" -expired -closed
site:jobs.ashbyhq.com "Software Engineer" -expired -closed
```

### Return Format

```json
{
  "status": "success",
  "total_found": 45,
  "total_new": 30,
  "by_platform": {
    "greenhouse": {
      "urls_found": 15,
      "jobs_scraped": 14,
      "jobs_imported": 10,
      "errors": 1
    },
    "lever": { ... },
    "ashby": { ... },
    "workable": { ... }
  },
  "duration_seconds": 45.3,
  "cost_usd": 0.00
}
```

### Integration with Database

The scanner seamlessly integrates with the existing importer system:

1. **URL Hash Check:** Skips jobs if URL already exists
2. **Fuzzy Hash Check:** Compares company+title for duplicates
3. **Priority Resolution:** ATS platforms (priority 1) replace LinkedIn/Glassdoor (priority 2)

**Example Deduplication:**
```
1. LinkedIn imports "AI Engineer at Scribd" (priority 2)
2. Lever finds same job "AI Engineer at Scribd" (priority 1)
   → Result: Lever version REPLACES LinkedIn version
```

### Configuration

The scanner uses these CSS selectors for each platform:

**Greenhouse:**
```python
'title': '.app-title, h1.job-title, [data-automation="job-title"]'
'company': '.company-name, [data-automation="company-name"]'
'location': '.location, [data-automation="job-location"]'
'description': '#content, .job-description, [data-automation="job-description"]'
```

**Lever:**
```python
'title': '.posting-headline h2, h1'
'company': '.posting-headline .company-name, .posting-categories .location'
'location': '.posting-categories .location, .sort-by-commitment'
'description': '.posting-description .section-wrapper, .posting-description'
```

### Rate Limiting

To avoid being blocked by search engines:

- **Default Delay:** 1 second between requests
- **Configurable:** Set `scanner.request_delay` to adjust
- **Search Strategy:** Uses DuckDuckGo HTML (less aggressive blocking than Google)

### Error Handling

The scanner gracefully handles:

- Missing or changed CSS selectors (multiple fallbacks)
- Network errors (logs and continues)
- Invalid HTML (skips and continues)
- Search engine blocking (returns partial results)

### Testing

**Unit Tests:**
```bash
# Run comprehensive test suite
python test_ats_scanner.py
```

**Demo:**
```bash
# Run interactive demo
python demo_ats_scanner.py
```

### Dependencies

```
beautifulsoup4>=4.12.0  # HTML parsing
aiohttp>=3.9.0          # Async HTTP requests
```

### Performance

- **Single Job Scrape:** ~2 seconds (includes 1s rate limit)
- **Full Scan:** 5-10 minutes (4 platforms × 24 job titles)
- **Memory Usage:** Minimal (~50MB)
- **CPU Usage:** Low (mostly I/O bound)

### Known Limitations

1. **Search Engine Rate Limits:** May be blocked if too many requests
   - **Mitigation:** Built-in delays, use DuckDuckGo

2. **Page Structure Changes:** ATS platforms may update HTML
   - **Mitigation:** Multiple CSS selectors, fallback extraction

3. **Search Accuracy:** May not find all jobs
   - **Mitigation:** Complements Antigravity scraping

### Future Enhancements

- Google Custom Search API integration (more reliable)
- Selenium/Playwright fallback for JavaScript-heavy pages
- Company-specific targeted searches
- Proxy rotation for higher throughput

---

**Status:** Production Ready ✅
**Last Updated:** 2026-01-29
**Maintainer:** Job Hunter AI Team

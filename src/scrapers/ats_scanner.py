"""
ATS Dorking Scanner

Automated Google dorking to find jobs on ATS platforms:
- Greenhouse (jobs.greenhouse.io)
- Lever (jobs.lever.co)
- Ashby (jobs.ashbyhq.com)
- Workable (apply.workable.com)

ATS platforms provide highest quality job listings (direct from companies).
"""

import asyncio
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

import aiohttp
from bs4 import BeautifulSoup

from src.core.database import Database
from src.core.importer import AntigravityImporter
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ATSScanner:
    """
    Google dorking scanner for ATS platforms.
    No Antigravity needed - direct scraping.
    """
    
    ATS_PLATFORMS = {
        'greenhouse': {
            'domain': 'jobs.greenhouse.io',
            'url_pattern': r'https://boards\.greenhouse\.io/[\w-]+/jobs/\d+',
            'priority': 1,
            'selectors': {
                'title': '.app-title, h1.job-title, [data-automation="job-title"]',
                'company': '.company-name, [data-automation="company-name"]',
                'location': '.location, [data-automation="job-location"]',
                'description': '#content, .job-description, [data-automation="job-description"]'
            }
        },
        'lever': {
            'domain': 'jobs.lever.co',
            'url_pattern': r'https://jobs\.lever\.co/[\w-]+/[\w-]+',
            'priority': 1,
            'selectors': {
                'title': '.posting-headline h2, h1',
                'company': '.posting-headline .company-name, .posting-categories .location',
                'location': '.posting-categories .location, .sort-by-commitment',
                'description': '.posting-description .section-wrapper, .posting-description'
            }
        },
        'ashby': {
            'domain': 'jobs.ashbyhq.com',
            'url_pattern': r'https://jobs\.ashbyhq\.com/[\w-]+/[\w-]+',
            'priority': 1,
            'selectors': {
                'title': 'h1, [data-testid="job-title"]',
                'company': '.company-name, [data-testid="company-name"]',
                'location': '.location, [data-testid="job-location"]',
                'description': '.job-description, [data-testid="job-description"]'
            }
        },
        'workable': {
            'domain': 'apply.workable.com',
            'url_pattern': r'https://apply\.workable\.com/[\w-]+/j/[\w]+',
            'priority': 1,
            'selectors': {
                'title': 'h1, .job-title',
                'company': '.company-name',
                'location': '.location',
                'description': '.job-description, .description'
            }
        }
    }
    
    def __init__(
        self,
        db: Optional[Database] = None,
        config_loader: Optional[ConfigLoader] = None
    ):
        """Initialize the ATS scanner.
        
        Args:
            db: Database instance
            config_loader: Config loader for preferences
        """
        self.db = db or Database()
        self.config_loader = config_loader or ConfigLoader()
        self.importer = AntigravityImporter(db=self.db)
        
        # Request settings
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Rate limiting
        self.request_delay = 1.0  # seconds between requests
    
    def _build_dork_query(
        self,
        job_title: str,
        platform: str,
        location: Optional[str] = None
    ) -> str:
        """Build Google dork query for ATS platform.
        
        Args:
            job_title: Job title to search for
            platform: Platform key (greenhouse, lever, etc.)
            location: Optional location filter
            
        Returns:
            Google dork query string
        """
        config = self.ATS_PLATFORMS.get(platform)
        if not config:
            raise ValueError(f"Unknown platform: {platform}")
        
        domain = config['domain']
        
        # Build query: site:jobs.lever.co "AI Engineer" "Remote"
        query_parts = [
            f'site:{domain}',
            f'"{job_title}"'
        ]
        
        if location:
            query_parts.append(f'"{location}"')
        
        # Exclude expired/closed listings
        query_parts.append('-expired -closed')
        
        return ' '.join(query_parts)
    
    async def _search_google(
        self,
        query: str,
        max_results: int = 50
    ) -> list[str]:
        """Execute Google search and extract URLs.
        
        Note: In production, use Google Custom Search API for reliability.
        This implementation uses direct scraping as a fallback.
        
        Args:
            query: Google search query
            max_results: Maximum results to return
            
        Returns:
            List of job URLs found
        """
        urls = []
        
        # Use Google Custom Search API if available
        # Fallback: Direct DuckDuckGo HTML scraping (more reliable than Google)
        try:
            encoded_query = quote_plus(query)
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    search_url,
                    headers=self.headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Search returned status {response.status}")
                        return urls
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract result links
                    for result in soup.select('.result__url, .result__a'):
                        href = result.get('href', '')
                        if not href:
                            # Try getting text content as URL
                            href = result.get_text(strip=True)
                        
                        # Filter for ATS domains
                        for platform, config in self.ATS_PLATFORMS.items():
                            if config['domain'] in href:
                                # Clean up URL
                                clean_url = self._extract_clean_url(href, platform)
                                if clean_url and clean_url not in urls:
                                    urls.append(clean_url)
                                    if len(urls) >= max_results:
                                        return urls
            
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
        
        return urls
    
    def _extract_clean_url(self, raw_url: str, platform: str) -> Optional[str]:
        """Extract and clean job URL from search result.
        
        Args:
            raw_url: Raw URL from search results
            platform: Platform identifier
            
        Returns:
            Clean job URL or None
        """
        config = self.ATS_PLATFORMS.get(platform)
        if not config:
            return None
        
        # Extract URL using platform pattern
        pattern = config['url_pattern']
        match = re.search(pattern, raw_url)
        
        if match:
            return match.group(0)
        
        # Fallback: Try to build URL from domain
        if config['domain'] in raw_url:
            parsed = urlparse(raw_url)
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        return None
    
    async def scrape_ats_job(
        self,
        url: str,
        platform: str
    ) -> Optional[dict]:
        """Scrape job details from ATS page.
        
        Args:
            url: Job page URL
            platform: Platform identifier
            
        Returns:
            Job data dict or None on failure
        """
        config = self.ATS_PLATFORMS.get(platform)
        if not config:
            logger.error(f"Unknown platform: {platform}")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=self.headers,
                    timeout=30
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: {response.status}")
                        return None
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
            
            selectors = config['selectors']
            
            # Extract job details
            title = self._extract_text(soup, selectors['title'])
            company = self._extract_text(soup, selectors['company'])
            location = self._extract_text(soup, selectors['location'])
            description = self._extract_text(soup, selectors['description'])
            
            if not title:
                logger.warning(f"Could not extract title from {url}")
                return None
            
            # If company not found, try to extract from URL
            if not company:
                company = self._extract_company_from_url(url, platform)
            
            return {
                'title': title,
                'company': company or 'Unknown',
                'location': location or 'Not specified',
                'url': url,
                'description': description or '',
                'external_id': self._generate_external_id(url),
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
            return None
    
    def _extract_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Extract text from element using CSS selector.
        
        Args:
            soup: BeautifulSoup object
            selector: CSS selector (comma-separated for multiple)
            
        Returns:
            Extracted text or None
        """
        for sel in selector.split(','):
            element = soup.select_one(sel.strip())
            if element:
                text = element.get_text(separator=' ', strip=True)
                if text:
                    return text
        return None
    
    def _extract_company_from_url(self, url: str, platform: str) -> Optional[str]:
        """Extract company name from URL path.
        
        Args:
            url: Job URL
            platform: Platform identifier
            
        Returns:
            Company name or None
        """
        try:
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if path_parts:
                # First path segment is usually company
                company = path_parts[0]
                # Convert slug to title case
                return company.replace('-', ' ').title()
        except Exception:
            pass
        
        return None
    
    def _generate_external_id(self, url: str) -> str:
        """Generate external ID from URL.
        
        Args:
            url: Job URL
            
        Returns:
            MD5 hash of URL
        """
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    async def scan_platform(
        self,
        platform: str,
        job_titles: list[str],
        max_results: int = 50,
        location: Optional[str] = None
    ) -> dict:
        """Scan a single ATS platform for jobs.
        
        Args:
            platform: Platform key
            job_titles: List of job titles to search
            max_results: Max results per title
            location: Optional location filter
            
        Returns:
            Scan results dict
        """
        results = {
            'platform': platform,
            'urls_found': 0,
            'jobs_scraped': 0,
            'jobs_imported': 0,
            'errors': 0
        }
        
        all_urls = set()
        
        # Search for each job title
        for title in job_titles:
            query = self._build_dork_query(title, platform, location)
            logger.info(f"Searching: {query}")
            
            urls = await self._search_google(query, max_results)
            all_urls.update(urls)
            
            # Rate limiting
            await asyncio.sleep(self.request_delay)
        
        results['urls_found'] = len(all_urls)
        logger.info(f"Found {len(all_urls)} unique URLs on {platform}")
        
        # Scrape each job
        for url in all_urls:
            job_data = await self.scrape_ats_job(url, platform)
            
            if job_data:
                results['jobs_scraped'] += 1
                
                # Import to database
                try:
                    # Use the _process_job method directly since we have a single job
                    # Get source from job_data
                    source = job_data.get('source', platform)

                    # Initialize source stats if needed
                    if source not in self.importer.stats['by_source']:
                        self.importer.stats['by_source'][source] = {
                            'total': 0,
                            'new': 0,
                            'url_dup': 0,
                            'fuzzy_dup_skip': 0,
                            'fuzzy_dup_update': 0
                        }

                    # Get count before processing
                    before_count = self.importer.stats['new_jobs']

                    # Process the job
                    self.importer._process_job(job_data, source)

                    # Check if a new job was added
                    if self.importer.stats['new_jobs'] > before_count:
                        results['jobs_imported'] += 1
                except Exception as e:
                    logger.error(f"Import error for {url}: {e}")
                    results['errors'] += 1
            else:
                results['errors'] += 1
            
            # Rate limiting
            await asyncio.sleep(self.request_delay)
        
        return results
    
    async def scan_all_platforms(
        self,
        job_titles: Optional[list[str]] = None,
        max_results_per_platform: int = 50,
        location: Optional[str] = None
    ) -> dict:
        """Scan all ATS platforms.
        
        Args:
            job_titles: Job titles to search (defaults from preferences)
            max_results_per_platform: Max results per platform
            location: Optional location filter
            
        Returns:
            Scan results dict
        """
        # Load job titles from preferences if not provided
        if not job_titles:
            prefs = self.config_loader.get_preferences()
            job_titles = prefs.target_positions if prefs.target_positions else ['Software Engineer']
        
        results = {
            'total_found': 0,
            'total_new': 0,
            'by_platform': {},
            'duration_seconds': 0,
            'cost_usd': 0.00  # ATS scanning is free
        }
        
        start_time = datetime.now()
        
        for platform in self.ATS_PLATFORMS.keys():
            logger.info(f"Scanning {platform}...")
            
            platform_result = await self.scan_platform(
                platform=platform,
                job_titles=job_titles,
                max_results=max_results_per_platform,
                location=location
            )
            
            results['by_platform'][platform] = platform_result
            results['total_found'] += platform_result['urls_found']
            results['total_new'] += platform_result['jobs_imported']
        
        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"ATS scan complete: {results['total_found']} found, "
            f"{results['total_new']} new in {results['duration_seconds']:.1f}s"
        )
        
        return results


# CLI support for testing
if __name__ == "__main__":
    import sys
    
    async def main():
        scanner = ATSScanner()
        
        # Test with single query
        platform = sys.argv[1] if len(sys.argv) > 1 else 'lever'
        title = sys.argv[2] if len(sys.argv) > 2 else 'AI Engineer'
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
        
        print(f"Testing ATS scanner: {platform} - '{title}' (limit: {limit})")
        
        result = await scanner.scan_platform(
            platform=platform,
            job_titles=[title],
            max_results=limit
        )
        
        print(f"Results: {result}")
    
    asyncio.run(main())

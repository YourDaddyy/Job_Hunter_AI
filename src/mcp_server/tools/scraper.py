"""Scraping tool for the MCP server.

This module provides the scrape_jobs_tool function which integrates
all three scrapers (LinkedIn, Indeed, Wellfound) and handles:
- Job scraping from multiple platforms
- Deduplication using database
- Statistics tracking
- Error handling for individual scraper failures
"""

import asyncio
from dataclasses import asdict
from typing import Dict, Any, List, Optional

from src.core.browser import BrowserManager
from src.core.database import Database
from src.scrapers.linkedin import LinkedInScraper
from src.scrapers.indeed import IndeedScraper
from src.scrapers.wellfound import WellfoundScraper
from src.scrapers.base import JobData, ScraperError, LoginError
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def scrape_jobs_tool(
    platform: str = "all",
    limit: int = 100,
    keywords: Optional[List[str]] = None,
    remote_only: bool = True
) -> Dict[str, Any]:
    """Scrape jobs from job platforms and save to database.

    This tool:
    1. Initializes browser and scrapers
    2. Scrapes jobs from selected platform(s)
    3. Checks for duplicates before inserting
    4. Saves new jobs to database
    5. Returns statistics

    Args:
        platform: "all", "linkedin", "indeed", or "wellfound" (default: "all")
        limit: Maximum jobs to scrape per platform (default: 100)
        keywords: Optional list of search keywords. If not provided, uses
                  target_positions from preferences.md
        remote_only: Filter for remote-only jobs (default: True)

    Returns:
        Dictionary with:
        - status: "success" or "partial_failure"
        - stats: Overall statistics
        - platform_results: Per-platform results
        - errors: List of error messages
    """
    logger.info(
        "Starting scrape_jobs_tool: platform=%s, limit=%d, keywords=%s, remote_only=%s",
        platform, limit, keywords, remote_only
    )

    # Initialize components
    db = Database()
    config_loader = ConfigLoader()

    # Get keywords from preferences if not provided
    if keywords is None:
        try:
            preferences = config_loader.get_preferences()
            keywords = preferences.target_positions
            logger.info("Using keywords from preferences: %s", keywords)
        except Exception as e:
            logger.warning("Could not load preferences, using default keywords: %s", e)
            keywords = ["Software Engineer", "AI Engineer", "Machine Learning Engineer"]

    # Overall statistics
    stats = {
        "jobs_found": 0,
        "jobs_new": 0,
        "jobs_duplicate": 0,
        "errors": 0
    }

    platform_results = {}
    errors = []

    # Determine which platforms to scrape
    platforms_to_scrape = []
    if platform == "all":
        platforms_to_scrape = ["linkedin", "indeed", "wellfound"]
    elif platform in ["linkedin", "indeed", "wellfound"]:
        platforms_to_scrape = [platform]
    else:
        return {
            "status": "error",
            "error": f"Invalid platform: {platform}. Must be 'all', 'linkedin', 'indeed', or 'wellfound'",
            "stats": stats,
            "platform_results": {},
            "errors": []
        }

    # Initialize browser manager
    browser = BrowserManager(headless=False)

    try:
        await browser.launch()
        logger.info("Browser launched successfully")

        # Scrape each platform
        for platform_name in platforms_to_scrape:
            logger.info("=" * 60)
            logger.info(f"Scraping {platform_name.upper()}")
            logger.info("=" * 60)

            platform_stats = {
                "jobs_found": 0,
                "jobs_new": 0,
                "jobs_duplicate": 0,
                "status": "pending"
            }

            try:
                # Initialize scraper for platform
                if platform_name == "linkedin":
                    scraper = LinkedInScraper(browser)
                elif platform_name == "indeed":
                    scraper = IndeedScraper(browser)
                elif platform_name == "wellfound":
                    scraper = WellfoundScraper(browser)
                else:
                    continue

                # Scrape jobs
                logger.info(f"Starting {platform_name} scrape with keywords: {keywords}")
                jobs = await scraper.scrape(keywords=keywords, limit=limit)
                logger.info(f"{platform_name}: scraped {len(jobs)} jobs")

                platform_stats["jobs_found"] = len(jobs)
                stats["jobs_found"] += len(jobs)

                # Process each job
                for job in jobs:
                    try:
                        # Check for duplicates
                        duplicate_check = db.check_duplicate(
                            platform=job.platform,
                            external_id=job.external_id,
                            url=job.url
                        )

                        if duplicate_check["is_duplicate"]:
                            logger.debug(
                                f"Duplicate job: {job.title} at {job.company} "
                                f"(reason: {duplicate_check['reason']})"
                            )
                            platform_stats["jobs_duplicate"] += 1
                            stats["jobs_duplicate"] += 1
                            continue

                        # Insert new job
                        job_dict = asdict(job)

                        # Convert datetime fields to strings for SQLite
                        if job_dict.get('scraped_at'):
                            job_dict['scraped_at'] = job_dict['scraped_at'].isoformat()
                        if job_dict.get('posted_date'):
                            job_dict['posted_date'] = job_dict['posted_date'].isoformat()

                        job_id = db.insert_job(job_dict)
                        logger.info(
                            f"Inserted job #{job_id}: {job.title} at {job.company}"
                        )
                        platform_stats["jobs_new"] += 1
                        stats["jobs_new"] += 1

                    except Exception as e:
                        logger.error(f"Error processing job: {e}", exc_info=True)
                        stats["errors"] += 1
                        errors.append(f"{platform_name}: Failed to process job - {str(e)}")
                        continue

                platform_stats["status"] = "success"
                logger.info(
                    f"{platform_name} complete: {platform_stats['jobs_new']} new, "
                    f"{platform_stats['jobs_duplicate']} duplicates"
                )

            except LoginError as e:
                logger.error(f"{platform_name} login failed: {e}")
                platform_stats["status"] = "login_failed"
                stats["errors"] += 1
                errors.append(f"{platform_name}: Login failed - {str(e)}")

            except ScraperError as e:
                logger.error(f"{platform_name} scraping failed: {e}")
                platform_stats["status"] = "scraping_failed"
                stats["errors"] += 1
                errors.append(f"{platform_name}: Scraping failed - {str(e)}")

            except Exception as e:
                logger.error(f"{platform_name} unexpected error: {e}", exc_info=True)
                platform_stats["status"] = "error"
                stats["errors"] += 1
                errors.append(f"{platform_name}: Unexpected error - {str(e)}")

            finally:
                platform_results[platform_name] = platform_stats

    except Exception as e:
        logger.error(f"Browser error: {e}", exc_info=True)
        errors.append(f"Browser error: {str(e)}")
        stats["errors"] += 1

    finally:
        # Close browser
        try:
            await browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")

    # Determine overall status
    if stats["errors"] > 0:
        overall_status = "partial_failure"
    else:
        overall_status = "success"

    logger.info("=" * 60)
    logger.info("SCRAPING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total jobs found: {stats['jobs_found']}")
    logger.info(f"New jobs: {stats['jobs_new']}")
    logger.info(f"Duplicates: {stats['jobs_duplicate']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)

    return {
        "status": overall_status,
        "stats": stats,
        "platform_results": platform_results,
        "errors": errors
    }

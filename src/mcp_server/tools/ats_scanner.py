"""
ATS Scanner MCP Tool

MCP wrapper for ATS platform dorking and scraping.
"""

from typing import Optional

from src.scrapers.ats_scanner import ATSScanner
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def scan_ats_platforms_tool(
    job_titles: Optional[list] = None,
    max_results_per_platform: int = 50,
    location: Optional[str] = None
) -> dict:
    """
    Scan ATS platforms for job listings via Google dorking.
    
    This tool automatically scrapes jobs from:
    - Greenhouse (jobs.greenhouse.io)
    - Lever (jobs.lever.co)
    - Ashby (jobs.ashbyhq.com)
    - Workable (apply.workable.com)
    
    ATS jobs are highest quality (direct from companies) and given priority=1.
    No Antigravity needed - fully automated.
    
    Args:
        job_titles: List of job titles to search. Defaults from preferences.md
        max_results_per_platform: Max results per platform per title
        location: Optional location filter (e.g., "Remote", "New York")
        
    Returns:
        dict with:
            - status: 'success' or 'error'
            - total_found: Total job URLs found
            - total_new: New jobs imported to database
            - by_platform: Results breakdown per platform
            - duration_seconds: Scan duration
            - message: Human-readable summary
    """
    try:
        logger.info("Starting ATS platform scan")
        
        scanner = ATSScanner()
        
        result = await scanner.scan_all_platforms(
            job_titles=job_titles,
            max_results_per_platform=max_results_per_platform,
            location=location
        )
        
        return {
            "status": "success",
            "total_found": result["total_found"],
            "total_new": result["total_new"],
            "by_platform": result["by_platform"],
            "duration_seconds": result["duration_seconds"],
            "cost_usd": 0.00,  # ATS scanning is free
            "message": f"ATS scan complete. Found {result['total_found']} jobs, "
                      f"imported {result['total_new']} new to database. "
                      f"Duration: {result['duration_seconds']:.1f}s"
        }
        
    except Exception as e:
        logger.error(f"ATS scan failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"ATS scan failed: {e}"
        }

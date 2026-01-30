"""
Report MCP Tool

MCP wrapper for campaign report generation.
"""

from datetime import datetime
from typing import Optional

from src.output.report_generator import CampaignReportGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_campaign_report_tool(date: Optional[str] = None) -> dict:
    """
    Generate daily campaign report with matched jobs.
    
    This tool creates a Markdown report showing:
    - HIGH MATCH JOBS (score ≥85) with resume links
    - MEDIUM MATCH JOBS (score 60-84) for user review
    - Statistics and cost breakdown
    
    Args:
        date: Optional date in YYYY-MM-DD format. Defaults to today.
        
    Returns:
        dict with:
            - status: 'success' or 'error'
            - report_path: Path to generated report
            - high_match_count: Number of high match jobs
            - medium_match_count: Number of medium match jobs
            - message: Human-readable summary
    """
    try:
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Generating campaign report for {date}")
        
        generator = CampaignReportGenerator()
        result = generator.generate_report(date)
        
        return {
            "status": "success",
            "report_path": result["report_path"],
            "high_match_count": result["high_match_count"],
            "medium_match_count": result["medium_match_count"],
            "total_processed": result["total_processed"],
            "message": f"Report generated at {result['report_path']}. "
                      f"Found {result['high_match_count']} HIGH matches (resumes ready) "
                      f"and {result['medium_match_count']} MEDIUM matches (need review)."
        }
        
    except Exception as e:
        logger.error(f"Failed to generate campaign report: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to generate report: {e}"
        }

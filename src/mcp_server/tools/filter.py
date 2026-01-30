"""Filter jobs MCP tool - GLM-based job filtering."""

import json
from mcp.types import TextContent

from src.core.filter import JobFilterService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def filter_jobs_with_glm_tool(
    limit: int = 100,
    batch_size: int = 10,
    force_refilter: bool = False
) -> list[TextContent]:
    """Filter jobs using GLM for intelligent scoring.
    
    Processes jobs with status='new' and scores them using GLM API.
    Jobs are automatically categorized based on score:
    - Score >= 0.85: Matched (auto-apply eligible)
    - Score 0.60-0.85: Matched (manual review)  
    - Score < 0.60: Rejected
    
    Args:
        limit: Maximum number of jobs to process (default: 100)
        batch_size: Number of jobs to process concurrently (default: 10)
        force_refilter: If True, re-filter already filtered jobs (default: False)
        
    Returns:
        List with single TextContent containing JSON results
        
    Example Response:
        {
            "success": true,
            "stats": {
                "total_processed": 50,
                "high_match": 5,
                "medium_match": 15,
                "rejected": 25,
                "pre_filtered": 5,
                "errors": 0,
                "cost_usd": 0.0523
            },
            "message": "Total: 50, High: 5, Medium: 15, Rejected: 25, ..."
        }
    """
    try:
        logger.info(
            f"Starting filter_jobs_with_glm: limit={limit}, "
            f"batch_size={batch_size}, force_refilter={force_refilter}"
        )
        
        # Initialize service
        service = JobFilterService()
        
        # Run filtering
        stats = await service.filter_new_jobs(
            batch_size=batch_size,
            limit=limit
        )
        
        # Format response
        result = {
            "success": True,
            "stats": {
                "total_processed": stats.total,
                "high_match": stats.high_match,
                "medium_match": stats.medium_match,
                "rejected": stats.rejected,
                "pre_filtered": stats.pre_filtered,
                "errors": stats.errors,
                "cost_usd": round(stats.cost_usd, 4)
            },
            "message": str(stats)
        }
        
        logger.info(f"Filter complete: {stats}")
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"filter_jobs_with_glm failed: {e}", exc_info=True)
        
        error_result = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

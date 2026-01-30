"""GLM Processor MCP tool - Three-tier job filtering system.

This tool processes unfiltered jobs with GLM and implements a three-tier scoring system:
- Tier 1 (≥85): Auto-generate resume → Ready to apply
- Tier 2 (60-84): Add to campaign report → Awaiting user decision
- Tier 3 (<60): Keep in database → Archived, no action
"""

import json
from mcp.types import TextContent

from src.core.gl_processor import GLMProcessor, ProcessorStats
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def process_jobs_with_glm_tool(
    batch_size: int = 20,
    limit: int = None,
    enable_semantic_dedup: bool = True,
    enable_tier1_resume: bool = True
) -> list[TextContent]:
    """Process unfiltered jobs with GLM three-tier filtering system.

    This tool:
    1. Queries jobs where is_processed=FALSE
    2. Loads achievements.md and preferences.md
    3. Calls GLM to score each job 0-100
    4. Implements three tiers:
       - ≥85: Generate resume (Tier 1)
       - 60-84: Add to report (Tier 2)
       - <60: Archive (Tier 3)
    5. Updates database: ai_score, ai_reasoning, is_processed=TRUE

    Args:
        batch_size: Number of jobs to process in parallel (default: 20)
        limit: Maximum number of jobs to process (None = all, default: None)
        enable_semantic_dedup: Enable semantic duplicate detection (default: True)
        enable_tier1_resume: Auto-generate resumes for Tier 1 jobs (default: True)

    Returns:
        List with single TextContent containing JSON results

    Example Response:
        {
            "success": true,
            "stats": {
                "total_processed": 50,
                "tier1_high_match": 8,
                "tier2_medium_match": 22,
                "tier3_low_match": 15,
                "resumes_generated": 8,
                "semantic_duplicates_found": 2,
                "errors": 3,
                "cost_usd": 0.0523
            },
            "message": "Total: 50, Tier 1: 8, Tier 2: 22, Tier 3: 15, ..."
        }
    """
    try:
        logger.info(
            f"Starting process_jobs_with_glm: batch_size={batch_size}, "
            f"limit={limit}, semantic_dedup={enable_semantic_dedup}, "
            f"tier1_resume={enable_tier1_resume}"
        )

        # Initialize processor
        processor = GLMProcessor()

        # Run processing
        stats = await processor.process_unfiltered_jobs(
            batch_size=batch_size,
            limit=limit,
            enable_semantic_dedup=enable_semantic_dedup,
            enable_tier1_resume=enable_tier1_resume
        )

        # Format response
        result = {
            "success": True,
            "stats": {
                "total_processed": stats.total_processed,
                "tier1_high_match": stats.tier1_high_match,
                "tier2_medium_match": stats.tier2_medium_match,
                "tier3_low_match": stats.tier3_low_match,
                "resumes_generated": stats.resumes_generated,
                "semantic_duplicates_found": stats.semantic_duplicates_found,
                "errors": stats.errors,
                "cost_usd": round(stats.cost_usd, 4)
            },
            "message": str(stats)
        }

        logger.info(f"GLM processing complete: {stats}")

        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        logger.error(f"process_jobs_with_glm failed: {e}", exc_info=True)

        error_result = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }

        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

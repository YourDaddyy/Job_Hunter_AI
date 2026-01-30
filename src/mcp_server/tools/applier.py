"""Apply to job MCP tool - Automated job application via Playwright."""

import json
from mcp.types import TextContent

from src.core.applier import JobApplierService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def apply_to_job_tool(
    job_id: int,
    resume_path: str = None
) -> list[TextContent]:
    """Apply to a job using Playwright automation.

    Automatically applies to jobs on supported platforms:
    - LinkedIn (Easy Apply)
    - Indeed (Indeed Apply)
    - Wellfound (AngelList)

    Args:
        job_id: Database ID of the job to apply for
        resume_path: Path to resume PDF (optional, uses generated resume if not provided)

    Returns:
        List with single TextContent containing JSON results

    Example Success Response:
        {
            "status": "success",
            "job_id": 123,
            "company": "TechCorp",
            "title": "Senior Software Engineer",
            "platform": "linkedin",
            "method": "easy_apply",
            "error": null,
            "screenshot_path": null
        }

    Example Failure Response:
        {
            "status": "failed",
            "job_id": 123,
            "company": "TechCorp",
            "title": "Senior Software Engineer",
            "platform": "linkedin",
            "method": "easy_apply",
            "error": "Easy Apply button not found - may require external application",
            "screenshot_path": "/path/to/screenshot.png"
        }
    """
    try:
        logger.info(f"Starting apply_to_job for job_id={job_id}")

        # Initialize service
        service = JobApplierService()

        # Apply to job
        result = await service.apply_to_job(job_id, resume_path)

        # Format response
        response = {
            "status": "success" if result.success else "failed",
            "job_id": result.job_id,
            "company": result.company,
            "title": result.title,
            "platform": result.platform,
            "method": result.method,
            "error": result.error,
            "screenshot_path": result.screenshot_path
        }

        if result.success:
            logger.info(
                f"Application successful: job_id={job_id}, "
                f"company={result.company}, method={result.method}"
            )
        else:
            logger.warning(
                f"Application failed: job_id={job_id}, "
                f"company={result.company}, error={result.error}"
            )

        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]

    except Exception as e:
        # Unexpected errors not caught by JobApplierService
        logger.error(f"apply_to_job failed: {e}", exc_info=True)

        error_response = {
            "status": "error",
            "job_id": job_id,
            "company": "Unknown",
            "title": "Unknown",
            "platform": "unknown",
            "method": "error",
            "error": str(e),
            "screenshot_path": None
        }

        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

"""Tailor resume MCP tool - Claude-based resume customization."""

import json
from mcp.types import TextContent

from src.core.tailor import ResumeTailoringService
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def tailor_resume_tool(
    job_id: int
) -> list[TextContent]:
    """Tailor resume for a specific job using Claude.
    
    Creates a customized resume by:
    1. Loading job details from database
    2. Loading base resume and achievements from config
    3. Using Claude to select relevant achievements and customize content
    4. Saving tailored resume to database
    
    Args:
        job_id: Database ID of the job to tailor for
        
    Returns:
        List with single TextContent containing JSON results
        
    Example Response:
        {
            "success": true,
            "job_id": 1,
            "resume_id": 5,
            "summary": "Experienced AI Engineer with 5+ years...",
            "selected_achievements": [
                {
                    "name": "AI Platform Development",
                    "company": "Company X",
                    "period": "2022 - Present",
                    "bullets": ["Built ML pipeline...", "Improved accuracy..."]
                }
            ],
            "highlighted_skills": ["Python", "Machine Learning", "AWS"],
            "tailoring_notes": "Selected achievements emphasizing ML experience...",
            "cost_usd": 0.0145
        }
    """
    try:
        logger.info(f"Starting tailor_resume for job_id={job_id}")
        
        # Initialize service
        service = ResumeTailoringService()
        
        # Run tailoring
        result = await service.tailor_resume_for_job(job_id)
        
        # Format response
        response = {
            "success": True,
            "job_id": result.job_id,
            "resume_id": result.resume_id,
            "pdf_path": result.pdf_path,
            "summary": result.summary,
            "selected_achievements": result.selected_achievements,
            "highlighted_skills": result.highlighted_skills,
            "tailoring_notes": result.tailoring_notes,
            "cost_usd": round(result.cost_usd, 4)
        }
        
        logger.info(
            f"Tailor complete: job_id={job_id}, resume_id={result.resume_id}, "
            f"cost=${result.cost_usd:.4f}"
        )
        
        return [TextContent(
            type="text",
            text=json.dumps(response, indent=2)
        )]
        
    except ValueError as e:
        # Job not found or validation error
        logger.error(f"Validation error in tailor_resume: {e}")
        
        error_response = {
            "success": False,
            "error": str(e),
            "error_type": "ValidationError"
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]
        
    except Exception as e:
        # Other errors (API failure, etc.)
        logger.error(f"tailor_resume failed: {e}", exc_info=True)
        
        error_response = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(error_response, indent=2)
        )]

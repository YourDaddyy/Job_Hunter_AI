"""
Application MCP Tool

MCP wrapper for application instruction generation.
"""

from typing import Optional

from src.agents.application_guide_generator import ApplicationGuideGenerator
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def generate_application_instructions_tool(
    campaign_date: Optional[str] = None
) -> dict:
    """
    Generate Antigravity instructions for auto-applying to approved jobs.
    
    Creates a JSON file with:
    - Platform-specific form filling instructions
    - Resume paths for each job
    - Rate limiting and safety controls
    - Pause-before-submit for user review
    
    Args:
        campaign_date: Date in YYYY-MM-DD format. Defaults to today.
        
    Returns:
        dict with:
            - status: 'success', 'no_jobs', or 'error'
            - instruction_file: Path to generated JSON file
            - applications_count: Number of applications in file
            - message: Human-readable summary
    """
    try:
        logger.info(f"Generating application instructions for {campaign_date or 'today'}")
        
        generator = ApplicationGuideGenerator()
        result = generator.generate_application_guide(campaign_date)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate application instructions: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to generate application instructions: {e}"
        }

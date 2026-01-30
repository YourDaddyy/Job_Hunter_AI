"""MCP Notification Tools - Telegram integration for job hunter.

This module provides Telegram notification tools for the MCP server,
enabling Claude Code to send notifications and prompt user decisions
via Telegram bot.
"""

import json
from mcp.types import TextContent

from src.core.telegram import TelegramBot
from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def send_telegram_notification_tool(
    message: str,
    parse_mode: str = "Markdown"
) -> list[TextContent]:
    """Send a Telegram notification.
    
    Sends a message to the configured Telegram chat via the TelegramBot.
    Useful for sending status updates, alerts, or custom messages from
    the job hunting workflow.
    
    Args:
        message: Message content to send
        parse_mode: Telegram parse mode - "Markdown", "HTML", or "MarkdownV2"
                   (default: "Markdown")
    
    Returns:
        List with single TextContent containing JSON result:
        {
            "status": "success" | "error",
            "message_id": int,
            "error": null | str
        }
    
    Example:
        result = await send_telegram_notification_tool(
            "Job scraping complete! Found 50 new jobs."
        )
    """
    try:
        logger.info(f"Sending Telegram notification: {message[:50]}...")
        
        # Initialize TelegramBot
        bot = TelegramBot()
        await bot.initialize()
        
        # Send message
        message_id = await bot.send_message(text=message, parse_mode=parse_mode)
        
        result = {
            "status": "success",
            "message_id": message_id
        }
        
        logger.info(f"Telegram notification sent successfully (message_id: {message_id})")
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"send_telegram_notification failed: {e}", exc_info=True)
        
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]


async def send_pending_decisions_to_telegram_tool() -> list[TextContent]:
    """Send pending job decisions to Telegram for user review.
    
    Queries the database for jobs with status='matched' and decision_type='manual'
    (medium-match jobs with scores 0.60-0.85), and sends each as an interactive
    Telegram message with inline approve/skip buttons.
    
    Returns:
        List with single TextContent containing JSON result:
        {
            "status": "success" | "error",
            "jobs_sent": int,
            "message_ids": [int, ...],
            "error": null | str
        }
    
    Example:
        result = await send_pending_decisions_to_telegram_tool()
        # Sends interactive messages for each pending job
    """
    try:
        logger.info("Sending pending decisions to Telegram")
        
        # Initialize services
        db = Database()
        bot = TelegramBot(db=db)
        await bot.initialize()
        
        # Get pending jobs (matched, manual decision, not yet decided)
        jobs = db.get_matched_jobs(
            min_score=0.60,
            max_score=0.85,
            status="matched",
            limit=100
        )
        
        # Filter to only manual-decision jobs that haven't been decided
        pending_jobs = [
            job for job in jobs
            if job.decision_type == 'manual' and job.decided_at is None
        ]
        
        logger.info(f"Found {len(pending_jobs)} jobs pending user decision")
        
        if not pending_jobs:
            result = {
                "status": "success",
                "jobs_sent": 0,
                "message_ids": [],
                "message": "No jobs pending decision"
            }
            
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        
        # Send notification for each job
        message_ids = []
        sent_count = 0
        
        for job in pending_jobs:
            try:
                msg_id = await bot.send_job_notification(
                    job_id=job.id,
                    notification_type="match"
                )
                
                if msg_id:
                    message_ids.append(msg_id)
                    sent_count += 1
                    logger.debug(f"Sent notification for job {job.id} (message_id: {msg_id})")
                else:
                    logger.warning(f"Failed to send notification for job {job.id}")
                    
            except Exception as e:
                logger.error(f"Error sending notification for job {job.id}: {e}")
                continue
        
        result = {
            "status": "success",
            "jobs_sent": sent_count,
            "message_ids": message_ids,
            "message": f"Sent {sent_count} job notifications to Telegram"
        }
        
        logger.info(f"Sent {sent_count}/{len(pending_jobs)} pending decisions to Telegram")
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        logger.error(f"send_pending_decisions_to_telegram failed: {e}", exc_info=True)
        
        error_result = {
            "status": "error",
            "jobs_sent": 0,
            "error": str(e),
            "error_type": type(e).__name__
        }
        
        return [TextContent(
            type="text",
            text=json.dumps(error_result, indent=2)
        )]

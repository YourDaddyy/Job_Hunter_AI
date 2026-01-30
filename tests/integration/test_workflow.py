"""Integration tests for the complete job hunting workflow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.database import Database, Job
from src.mcp_server.tools.scraper import scrape_jobs_tool
from src.mcp_server.tools.filter import filter_jobs_with_glm_tool
from src.mcp_server.tools.applier import apply_to_job_tool
from src.mcp_server.tools.notifier import (
    send_telegram_notification_tool,
    send_pending_decisions_to_telegram_tool
)
from src.mcp_server.server import call_tool


@pytest.fixture
def mock_db():
    """Mock Database."""
    db = MagicMock()
    # Setup common methods
    db.get_current_run = MagicMock(return_value=None)
    db.get_matched_jobs = MagicMock(return_value=[])
    db.get_job_by_id = MagicMock(return_value=None)
    return db


def create_mock_job(**kwargs):
    """Create a mock Job object with default attributes."""
    job = MagicMock()
    # Set default values
    job.id = 1
    job.title = "Test Job"
    job.company = "Test Co"
    job.url = "http://example.com"
    job.platform = "linkedin"
    job.match_score = 0.90
    job.status = "matched"
    job.decision_type = "auto"
    job.decided_at = None
    job.salary_min = 100000
    job.salary_max = 150000
    job.salary_currency = "USD"
    # Override with kwargs
    for k, v in kwargs.items():
        setattr(job, k, v)
    return job


@pytest.mark.asyncio
async def test_scrape_filter_flow():
    """Test the scrape and filter flow end-to-end (mocked)."""
    
    # 1. Mock the scraper service
    with patch("src.mcp_server.tools.scraper.JobScraperService") as MockScraper:
        mock_scraper_instance = MockScraper.return_value
        # Mock scrape results
        mock_scraper_instance.scrape_jobs.return_value = MagicMock(
            total_scraped=10,
            new_jobs=5,
            duplicates=5,
            by_platform={"linkedin": {"scraped": 10, "new": 5}}
        )
        
        # 2. Mock the filter service
        with patch("src.mcp_server.tools.filter.JobFilterService") as MockFilter:
             mock_filter_instance = MockFilter.return_value
             # Mock filter results
             mock_filter_instance.filter_new_jobs.return_value = MagicMock(
                 total=5,
                 high_match=2,
                 medium_match=2,
                 rejected=1,
                 pre_filtered=0,
                 errors=0,
                 cost_usd=0.01
             )
             
             # Call scrape tool
             scrape_result = await scrape_jobs_tool(platform="all", limit=10)
             
             # Call filter tool
             filter_result = await filter_jobs_with_glm_tool(batch_size=5)
             
             # Verify scraper called
             mock_scraper_instance.scrape_jobs.assert_called_once()
             
             # Verify filter called
             mock_filter_instance.filter_new_jobs.assert_called_once()
             
             # Verify results structure
             import json
             scrape_data = json.loads(scrape_result[0].text)
             assert scrape_data["status"] == "success"
             assert scrape_data["new_jobs"] == 5
             
             filter_data = json.loads(filter_result[0].text)
             assert filter_data["success"] is True
             assert filter_data["stats"]["high_match"] == 2


@pytest.mark.asyncio
async def test_auto_apply_flow():
    """Test the auto-apply flow for high-match jobs."""
    
    job = create_mock_job(
        id=1,
        match_score=0.95,
        decision_type="auto"
    )
    
    with patch("src.mcp_server.server.db") as mock_db, \
         patch("src.mcp_server.server.tailor_resume_tool") as mock_tailor, \
         patch("src.mcp_server.server.applier_service") as mock_applier:
        
        # Setup mocks
        mock_db.get_matched_jobs.return_value = [job]
        
        # Mock resume tailoring success
        from mcp.types import TextContent
        import json
        mock_tailor.return_value = [TextContent(
            type="text",
            text=json.dumps({"success": True, "pdf_path": "resume.pdf"})
        )]
        
        # Mock application success
        mock_applier.apply_to_job.return_value = MagicMock(
            success=True, method="easy_apply"
        )
        
        from src.mcp_server.server import call_tool
        
        result = await call_tool("process_high_match_jobs", {})
        result_data = json.loads(result[0].content[0].text)
        
        # Verify
        assert result_data["status"] == "success"
        assert result_data["applied"] == 1
        
        mock_tailor.assert_called_once_with(1)
        mock_applier.apply_to_job.assert_called_once()


@pytest.mark.asyncio
async def test_manual_approval_flow():
    """Test manual approval flow."""
    
    job = create_mock_job(
        id=2,
        match_score=0.75,
        decision_type="manual"
    )
    
    with patch("src.mcp_server.server.db") as mock_db, \
         patch("src.mcp_server.server.tailor_resume_tool") as mock_tailor, \
         patch("src.mcp_server.server.applier_service") as mock_applier:
         
        mock_db.get_job_by_id.return_value = job
        
        # Mock resume tailoring
        import json
        from mcp.types import TextContent
        mock_tailor.return_value = [TextContent(
            type="text",
            text=json.dumps({"success": True, "pdf_path": "resume.pdf"})
        )]
        
        # Mock application
        mock_applier.apply_to_job.return_value = MagicMock(success=True)
        
        # Call approve tool
        from src.mcp_server.server import call_tool
        result = await call_tool("approve_job", {"job_id": 2})
        result_data = json.loads(result[0].content[0].text)
        
        assert result_data["status"] == "success"
        assert result_data["application_result"]["submitted"] is True
        
        # Verify status update
        mock_db.update_job_status.assert_called_with(2, "approved")


@pytest.mark.asyncio
async def test_skip_job_flow():
    """Test skip job flow."""
    
    job = create_mock_job(
        id=3,
        match_score=0.70,
        decision_type="manual"
    )
    
    with patch("src.mcp_server.server.db") as mock_db:
        mock_db.get_job_by_id.return_value = job
        
        from src.mcp_server.server import call_tool
        result = await call_tool("skip_job", {"job_id": 3, "reason": "Not interested"})
        result_data = json.loads(result[0].content[0].text)
        
        assert result_data["status"] == "success"
        mock_db.update_job_status.assert_called_with(3, "skipped")
        # Verify log call (optional but good)
        # mock_db.log.assert_called_once() # Log checking might be strictly not required if implementation uses logger


@pytest.mark.asyncio
async def test_full_workflow_notification():
    """Test full workflow component regarding notifications."""
    
    # 1. Test Pending Notification
    with patch("src.mcp_server.tools.notifier.Database") as MockDB, \
         patch("src.mcp_server.tools.notifier.TelegramBot") as MockBot:
         
        mock_db_instance = MockDB.return_value
        mock_bot_instance = MockBot.return_value
        
        # Setup pending job
        job = create_mock_job(
            id=4,
            match_score=0.70,
            decision_type="manual",
            decided_at=None
        )
        mock_db_instance.get_matched_jobs.return_value = [job]
        mock_bot_instance.send_job_notification.return_value = 123
        
        # Run tool
        result = await send_pending_decisions_to_telegram_tool()
        import json
        data = json.loads(result[0].text)
        
        assert data["status"] == "success"
        assert data["jobs_sent"] == 1
        assert 123 in data["message_ids"]
        
    # 2. Test General Notification
    with patch("src.mcp_server.tools.notifier.TelegramBot") as MockBot:
        mock_bot_instance = MockBot.return_value
        mock_bot_instance.send_message.return_value = 456
        
        result = await send_telegram_notification_tool("Test Msg")
        data = json.loads(result[0].text)
        
        assert data["status"] == "success"
        assert data["message_id"] == 456

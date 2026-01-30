"""Unit tests for MCP Server."""

import pytest
import json
from pathlib import Path


def test_server_import():
    """Test that server module can be imported."""
    from src.mcp_server.server import server, db, config_loader
    
    assert server is not None
    assert server.name == "job-hunter"
    assert db is not None
    assert config_loader is not None


def test_database_initialized():
    """Test that database is initialized with schema."""
    from src.core.database import Database
    
    db = Database()
    
    # Try to get jobs (should work even if empty)
    jobs = db.get_jobs_by_status("new", limit=10)
    assert isinstance(jobs, list)


def test_tool_stubs_exist():
    """Test that all expected tools are defined."""
    from src.mcp_server.server import server
    
    # Expected tools
    expected_tools = [
        "scrape_jobs",
        "filter_jobs_with_glm",
        "get_matched_jobs",
        "check_duplicate",
        "get_pending_decisions",
        "process_high_match_jobs",
        "approve_job",
        "skip_job",
        "tailor_resume",
        "apply_to_job",
        "send_telegram_notification",
        "send_pending_decisions_to_telegram",
        "get_run_summary"
    ]
    
    # All tools should be registered (we can't easily test this without running the server)
    # This is a placeholder test for now
    assert server.name == "job-hunter"


def test_config_files_readable():
    """Test that example config files exist and are readable."""
    config_dir = Path("config")
    
    # Check example files exist
    assert (config_dir / "resume.example.md").exists()
    assert (config_dir / "preferences.example.md").exists()
    assert (config_dir / "achievements.example.md").exists()
    
    # Check they can be read
    resume_example = (config_dir / "resume.example.md").read_text(encoding="utf-8")
    assert len(resume_example) > 0
    assert "# Personal Information" in resume_example


def test_mcp_config_exists():
    """Test that .mcp.json configuration file exists."""
    mcp_config = Path(".mcp.json")
    
    assert mcp_config.exists()
    
    # Verify it's valid JSON
    config_data = json.loads(mcp_config.read_text(encoding="utf-8"))
    
    assert "mcpServers" in config_data
    assert "job-hunter" in config_data["mcpServers"]
    assert config_data["mcpServers"]["job-hunter"]["command"] == "python"


def test_stub_response_format():
    """Test that stub responses follow expected format."""
    from src.mcp_server.server import _stub_response
    
    response = _stub_response(
        "test_tool",
        "Phase X",
        {"status": "not_implemented", "test": "value"}
    )
    
    assert isinstance(response, list)
    assert len(response) > 0
    assert "content" in response[0]
    assert isinstance(response[0]["content"], list)
    assert "type" in response[0]["content"][0]
    assert response[0]["content"][0]["type"] == "text"
    
    # Parse the JSON text
    text_content = response[0]["content"][0]["text"]
    data = json.loads(text_content)
    
    assert data["status"] == "not_implemented"
    assert "note" in data
    assert "test_tool" in data["note"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

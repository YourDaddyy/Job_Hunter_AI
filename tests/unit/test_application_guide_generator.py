"""Tests for Application Guide Generator."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from src.agents.application_guide_generator import ApplicationGuideGenerator
from src.core.database import Database, Job
from src.utils.config import ConfigLoader
from src.utils.markdown_parser import PersonalInfo, Resume


@pytest.fixture
def mock_db():
    """Mock database with test jobs."""
    db = Mock(spec=Database)

    # Mock high match jobs (score â‰?0.85, decision_type='auto')
    high_match_job = Job(
        id=1,
        external_id="job1",
        platform="lever",
        url="https://jobs.lever.co/scribd/ai-engineer",
        url_hash="hash1",
        fuzzy_hash="fuzzy1",
        title="AI Engineer",
        company="Scribd",
        location="Remote",
        salary_min=120000,
        salary_max=160000,
        salary_currency="USD",
        remote_type="Remote",
        visa_sponsorship=False,
        easy_apply=False,
        jd_markdown="Job description...",
        jd_raw="Raw description...",
        match_score=0.92,
        match_reasoning="Excellent match",
        key_requirements=["Python", "ML"],
        red_flags=[],
        status="matched",
        decision_type="auto",
        source="lever",
        source_priority=1,
        is_processed=True,
        scraped_at=datetime.strptime("2026-01-29", "%Y-%m-%d"),
        filtered_at=None,
        decided_at=None,
        applied_at=None
    )

    # Mock approved medium match job (score 0.60-0.84, status='approved')
    medium_match_job = Job(
        id=2,
        external_id="job2",
        platform="greenhouse",
        url="https://jobs.greenhouse.io/anthropic/ml-engineer",
        url_hash="hash2",
        fuzzy_hash="fuzzy2",
        title="ML Engineer",
        company="Anthropic",
        location="San Francisco, CA",
        salary_min=140000,
        salary_max=180000,
        salary_currency="USD",
        remote_type="Hybrid",
        visa_sponsorship=True,
        easy_apply=False,
        jd_markdown="Job description...",
        jd_raw="Raw description...",
        match_score=0.78,
        match_reasoning="Good match with some reservations",
        key_requirements=["PyTorch", "Transformers"],
        red_flags=["Requires relocation"],
        status="approved",
        decision_type="manual",
        source="greenhouse",
        source_priority=1,
        is_processed=True,
        scraped_at=datetime.strptime("2026-01-29", "%Y-%m-%d"),
        filtered_at=None,
        decided_at=None,
        applied_at=None
    )

    db.get_matched_jobs.return_value = [high_match_job]
    db.get_jobs_by_status.return_value = [medium_match_job]

    return db


@pytest.fixture
def mock_config():
    """Mock config loader with test data."""
    config = Mock(spec=ConfigLoader)

    # Mock credentials
    personal_info = PersonalInfo(
        name="John Doe",
        email="john.doe@example.com",
        phone="+1-555-123-4567",
        title="AI Engineer",
        linkedin="https://linkedin.com/in/johndoe",
        github="https://github.com/johndoe",
        location="San Francisco, CA",
        visa_status="US Citizen"
    )

    resume = Mock(spec=Resume)
    resume.personal_info = personal_info

    config.get_credentials.return_value = Mock()
    config.get_resume.return_value = resume

    return config


def test_generate_application_guide_success(mock_db, mock_config, tmp_path):
    """Test successful application guide generation."""
    # Setup
    generator = ApplicationGuideGenerator(db=mock_db, config_loader=mock_config)
    generator.output_dir = tmp_path / "instructions"
    generator.output_dir.mkdir()

    # Execute
    result = generator.generate_application_guide(campaign_date="2026-01-29")

    # Verify result
    assert result["status"] == "success"
    assert result["applications_count"] == 2
    assert result["high_match"] == 1
    assert result["medium_approved"] == 1
    assert "antigravity run" in result["message"]

    # Verify file was created
    instruction_file = Path(result["instruction_file"])
    assert instruction_file.exists()

    # Verify JSON structure
    with open(instruction_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert data["_metadata"]["task_type"] == "apply_to_jobs"
    assert data["_metadata"]["campaign_date"] == "2026-01-29"
    assert len(data["applications"]) == 2

    # Verify safety features
    assert data["rate_limit"]["max_applications_per_hour"] == 5
    assert data["rate_limit"]["delay_between_applications_seconds"] == 300
    assert data["safety"]["pause_before_submit"] is True
    assert data["safety"]["user_confirmation_required"] is True

    # Verify first application (HIGH match)
    app1 = data["applications"][0]
    assert app1["job_id"] == 1
    assert app1["company"] == "Scribd"
    assert app1["title"] == "AI Engineer"
    assert app1["platform_type"] == "lever"
    assert app1["pause_before_submit"] is True
    assert "Navigate to https://jobs.lever.co/scribd/ai-engineer" in app1["instructions"]
    assert "output/Scribd_AI_Engineer.pdf" in app1["resume_path"]

    # Verify second application (MEDIUM approved)
    app2 = data["applications"][1]
    assert app2["job_id"] == 2
    assert app2["company"] == "Anthropic"
    assert app2["title"] == "ML Engineer"
    assert app2["platform_type"] == "greenhouse"
    assert app2["pause_before_submit"] is True


def test_generate_application_guide_no_jobs(mock_db, mock_config):
    """Test when no approved jobs are found."""
    # Setup - return empty lists
    mock_db.get_matched_jobs.return_value = []
    mock_db.get_jobs_by_status.return_value = []

    generator = ApplicationGuideGenerator(db=mock_db, config_loader=mock_config)

    # Execute
    result = generator.generate_application_guide(campaign_date="2026-01-29")

    # Verify
    assert result["status"] == "no_jobs"
    assert result["applications_count"] == 0
    assert result["instruction_file"] is None
    assert "No approved jobs found" in result["message"]


def test_platform_detection():
    """Test platform detection from URLs."""
    generator = ApplicationGuideGenerator()

    test_cases = [
        ("https://jobs.greenhouse.io/company/job", "greenhouse"),
        ("https://jobs.lever.co/company/job", "lever"),
        ("https://jobs.ashbyhq.com/company/job", "ashby"),
        ("https://apply.workable.com/company/j/job", "workable"),
        ("https://www.linkedin.com/jobs/view/123", "linkedin"),
        ("https://www.indeed.com/viewjob?jk=123", "indeed"),
        ("https://www.glassdoor.com/job/123", "glassdoor"),
        ("https://example.com/careers/job", "generic"),
    ]

    for url, expected_platform in test_cases:
        assert generator._detect_platform_type(url) == expected_platform


def test_form_instructions_greenhouse(mock_config):
    """Test Greenhouse-specific form instructions."""
    generator = ApplicationGuideGenerator(config_loader=mock_config)

    job = {
        'id': 1,
        'company': 'TestCo',
        'title': 'Engineer',
        'url': 'https://jobs.greenhouse.io/testco/engineer'
    }

    personal_info = PersonalInfo(
        name="John Doe",
        email="john@example.com",
        phone="555-1234",
        linkedin="https://linkedin.com/in/johndoe"
    )

    instructions = generator._generate_form_instructions(job, personal_info)

    # Verify Greenhouse-specific content
    assert "First Name: John" in instructions
    assert "Last Name: Doe" in instructions
    assert "Email: john@example.com" in instructions
    assert "Phone: 555-1234" in instructions
    assert "PAUSE at Submit button" in instructions
    assert "output/TestCo_Engineer.pdf" in instructions


def test_form_instructions_lever(mock_config):
    """Test Lever-specific form instructions."""
    generator = ApplicationGuideGenerator(config_loader=mock_config)

    job = {
        'id': 1,
        'company': 'Scribd',
        'title': 'AI Engineer',
        'url': 'https://jobs.lever.co/scribd/ai-engineer'
    }

    personal_info = PersonalInfo(
        name="Jane Smith",
        email="jane@example.com",
        phone="555-5678"
    )

    instructions = generator._generate_form_instructions(job, personal_info)

    # Verify Lever-specific content
    assert "Apply for this job" in instructions
    assert "Full Name: Jane Smith" in instructions
    assert "Email: jane@example.com" in instructions
    assert "PAUSE at Submit button" in instructions


def test_form_instructions_linkedin_easy_apply(mock_config):
    """Test LinkedIn Easy Apply instructions."""
    generator = ApplicationGuideGenerator(config_loader=mock_config)

    job = {
        'id': 1,
        'company': 'LinkedIn',
        'title': 'Developer',
        'url': 'https://www.linkedin.com/jobs/view/12345'
    }

    personal_info = PersonalInfo(
        name="Bob Johnson",
        email="bob@example.com",
        phone="555-9999"
    )

    instructions = generator._generate_form_instructions(job, personal_info)

    # Verify LinkedIn-specific content
    assert "Easy Apply" in instructions
    assert "Step through wizard" in instructions
    assert "PAUSE at final Submit/Review step" in instructions


def test_resume_path_generation():
    """Test resume path generation."""
    generator = ApplicationGuideGenerator()

    job = {
        'company': 'Test Company With Spaces',
        'title': 'Senior Software Engineer / Developer'
    }

    path = generator._get_resume_path(job)

    # Should sanitize company and title
    assert path.startswith("output/")
    assert path.endswith(".pdf")
    assert "Test_Company_With_Sp" in path  # Truncated to 20 chars
    assert "Senior_Software_Engi" in path  # Truncated to 20 chars
    assert "/" not in path.replace("output/", "").replace(".pdf", "")  # No slashes


def test_default_date():
    """Test that default date is today."""
    generator = ApplicationGuideGenerator()

    with patch.object(generator.db, 'get_matched_jobs', return_value=[]):
        with patch.object(generator.db, 'get_jobs_by_status', return_value=[]):
            result = generator.generate_application_guide()

            # Should use today's date
            today = datetime.now().strftime('%Y-%m-%d')
            assert result["status"] == "no_jobs"


def test_rate_limiting_in_output(mock_db, mock_config, tmp_path):
    """Test that rate limiting is properly configured in output."""
    generator = ApplicationGuideGenerator(db=mock_db, config_loader=mock_config)
    generator.output_dir = tmp_path / "instructions"
    generator.output_dir.mkdir()

    result = generator.generate_application_guide(campaign_date="2026-01-29")

    # Read output file
    with open(result["instruction_file"], 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Verify rate limiting
    assert data["rate_limit"]["max_applications_per_hour"] == 5
    assert data["rate_limit"]["delay_between_applications_seconds"] == 300

    # Verify each application has rate limit
    for app in data["applications"]:
        assert app["rate_limit_seconds"] == 300
        assert app["pause_before_submit"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

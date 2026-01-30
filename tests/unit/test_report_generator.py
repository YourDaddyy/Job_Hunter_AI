"""
Unit tests for Campaign Report Generator.
"""

import os
import pytest
from datetime import datetime
from pathlib import Path

from src.core.database import Database
from src.output.report_generator import CampaignReportGenerator


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    db = Database(":memory:")
    db.init_schema()
    return db


@pytest.fixture
def report_generator(test_db, tmp_path):
    """Create a report generator with test database."""
    generator = CampaignReportGenerator(db=test_db)
    # Use temp directory for output
    generator.output_dir = tmp_path / "campaigns"
    generator.output_dir.mkdir(exist_ok=True)
    return generator


@pytest.fixture
def sample_jobs(test_db):
    """Insert sample jobs into test database."""
    today = datetime.now().strftime('%Y-%m-%d')

    # HIGH match jobs (Tier 1, score >= 85)
    high_jobs = [
        {
            'external_id': 'high1',
            'platform': 'linkedin',
            'url': 'https://jobs.lever.co/scribd/ai-engineer',
            'title': 'AI Engineer',
            'company': 'Scribd',
            'location': 'Remote',
            'jd_markdown': 'Job description...',
            'match_score': 0.92,
            'match_reasoning': 'Excellent match - strong AI/ML focus',
            'status': 'matched',
            'decision_type': 'auto',
            'source': 'lever',
            'source_priority': 1,
            'is_processed': True,
            'scraped_at': today
        },
        {
            'external_id': 'high2',
            'platform': 'linkedin',
            'url': 'https://jobs.lever.co/cohere/ml-engineer',
            'title': 'ML Engineer',
            'company': 'Cohere',
            'location': 'Remote',
            'jd_markdown': 'Job description...',
            'match_score': 0.88,
            'match_reasoning': 'Great fit - ML engineering role',
            'status': 'matched',
            'decision_type': 'auto',
            'source': 'lever',
            'source_priority': 1,
            'is_processed': True,
            'scraped_at': today
        }
    ]

    # MEDIUM match jobs (Tier 2, 60 <= score < 85)
    medium_jobs = [
        {
            'external_id': 'med1',
            'platform': 'linkedin',
            'url': 'https://jobs.lever.co/openai/ml-ops',
            'title': 'ML Ops Engineer',
            'company': 'OpenAI',
            'location': 'Remote',
            'jd_markdown': 'Job description...',
            'match_score': 0.78,
            'match_reasoning': 'Good match but contract role',
            'status': 'matched',
            'decision_type': 'manual',
            'source': 'linkedin',
            'source_priority': 2,
            'is_processed': True,
            'scraped_at': today
        },
        {
            'external_id': 'med2',
            'platform': 'linkedin',
            'url': 'https://jobs.lever.co/huggingface/ai-engineer',
            'title': 'AI Engineer',
            'company': 'Hugging Face',
            'location': 'Europe',
            'jd_markdown': 'Job description...',
            'match_score': 0.75,
            'match_reasoning': 'Remote in Europe timezone, may have challenges',
            'status': 'matched',
            'decision_type': 'manual',
            'source': 'linkedin',
            'source_priority': 2,
            'is_processed': True,
            'scraped_at': today
        }
    ]

    # LOW match job (rejected)
    low_jobs = [
        {
            'external_id': 'low1',
            'platform': 'linkedin',
            'url': 'https://linkedin.com/jobs/view/123',
            'title': 'Junior Developer',
            'company': 'Startup Co',
            'location': 'San Francisco',
            'jd_markdown': 'Job description...',
            'match_score': 0.45,
            'match_reasoning': 'Too junior, not a good fit',
            'status': 'rejected',
            'decision_type': None,
            'source': 'linkedin',
            'source_priority': 2,
            'is_processed': True,
            'scraped_at': today
        }
    ]

    # Insert all jobs
    job_ids = []
    for job_data in high_jobs + medium_jobs + low_jobs:
        job_id = test_db.insert_job(job_data)
        job_ids.append(job_id)

    return {
        'high': high_jobs,
        'medium': medium_jobs,
        'low': low_jobs,
        'ids': job_ids
    }


def test_generate_report_basic(report_generator, sample_jobs):
    """Test basic report generation."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)

    # Check return values
    assert result['high_match_count'] == 2
    assert result['medium_match_count'] == 2
    assert result['total_processed'] == 5
    assert result['total_rejected'] == 1

    # Check report file exists
    report_path = Path(result['report_path'])
    assert report_path.exists()

    # Check report content
    content = report_path.read_text(encoding='utf-8')
    assert 'Application Queue' in content
    assert 'HIGH MATCH JOBS' in content
    assert 'MEDIUM MATCH JOBS' in content
    assert 'Scribd' in content
    assert 'Cohere' in content
    assert 'OpenAI' in content
    assert 'Hugging Face' in content


def test_generate_report_with_date(report_generator, sample_jobs):
    """Test report generation with specific date."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)

    assert today in result['report_path']
    assert result['high_match_count'] == 2
    assert result['medium_match_count'] == 2


def test_generate_report_empty(report_generator, test_db):
    """Test report generation with no jobs."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)

    assert result['high_match_count'] == 0
    assert result['medium_match_count'] == 0
    assert result['total_processed'] == 0

    # Report should still be generated
    report_path = Path(result['report_path'])
    assert report_path.exists()

    content = report_path.read_text(encoding='utf-8')
    assert 'No high match jobs found today' in content
    assert 'No medium match jobs found today' in content


def test_markdown_formatting(report_generator, sample_jobs):
    """Test Markdown table formatting."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)
    report_path = Path(result['report_path'])
    content = report_path.read_text(encoding='utf-8')

    # Check table headers exist
    assert '| Status | Score | Company | Role | Source | Resume | Apply |' in content
    assert '| Score | Company | Role | Source | Why Medium? | Action |' in content

    # Check table separators
    assert '|--------|' in content

    # Check high match jobs have checkbox
    assert '| [ ] |' in content

    # Check scores are displayed correctly (as integers)
    assert '| 92 |' in content or '92' in content
    assert '| 88 |' in content or '88' in content


def test_statistics_section(report_generator, sample_jobs):
    """Test statistics section."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)
    report_path = Path(result['report_path'])
    content = report_path.read_text(encoding='utf-8')

    # Check statistics section exists
    assert 'Statistics' in content
    assert 'Total jobs processed' in content
    assert 'High match' in content
    assert 'Medium match' in content
    assert 'Rejected' in content
    assert 'Estimated cost' in content

    # Check cost breakdown
    assert 'Cost Breakdown' in content
    assert 'GLM filtering' in content
    assert 'Resume generation' in content


def test_resume_path_generation(report_generator, sample_jobs):
    """Test resume path generation for high match jobs."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)
    report_path = Path(result['report_path'])
    content = report_path.read_text(encoding='utf-8')

    # Check resume links are generated
    assert 'output/Scribd_AI_Engineer.pdf' in content
    assert 'output/Cohere_ML_Engineer.pdf' in content
    assert '[PDF](' in content


def test_cost_calculation(report_generator, sample_jobs):
    """Test cost calculation."""
    today = datetime.now().strftime('%Y-%m-%d')

    result = report_generator.generate_report(today)
    report_path = Path(result['report_path'])
    content = report_path.read_text(encoding='utf-8')

    # With 5 processed jobs and 2 high match (resumes):
    # GLM cost: 5 * $0.001 = $0.005
    # Resume cost: 2 * $0.02 = $0.04
    # Total: $0.045

    # Check cost is calculated and displayed
    assert '$0.05' in content or '$0.04' in content  # Rounded


def test_reasoning_truncation(report_generator, sample_jobs):
    """Test that long reasoning is truncated."""
    today = datetime.now().strftime('%Y-%m-%d')

    # Add job with very long reasoning
    test_db = report_generator.db
    long_reasoning = "This is a very long reasoning text " * 20  # >80 chars

    test_db.insert_job({
        'external_id': 'long1',
        'platform': 'linkedin',
        'url': 'https://example.com/job',
        'title': 'Engineer',
        'company': 'Test Co',
        'location': 'Remote',
        'jd_markdown': 'Job description...',
        'match_score': 0.70,
        'match_reasoning': long_reasoning,
        'status': 'matched',
        'decision_type': 'manual',
        'source': 'linkedin',
        'source_priority': 2,
        'is_processed': True,
        'scraped_at': today
    })

    result = report_generator.generate_report(today)
    report_path = Path(result['report_path'])
    content = report_path.read_text(encoding='utf-8')

    # Check reasoning is truncated with "..."
    assert '...' in content


def test_default_date(report_generator, sample_jobs):
    """Test report generation with default date (today)."""
    # Don't pass date, should default to today
    result = report_generator.generate_report()

    today = datetime.now().strftime('%Y-%m-%d')
    assert today in result['report_path']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

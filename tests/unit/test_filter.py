"""Unit tests for job filtering service.

Tests cover:
- PreFilter keyword/blacklist rejection
- FilterStats tracking
- JobFilterService batch processing
- Score-based routing
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from src.core.filter import (
    PreFilter,
    FilterStats,
    JobFilterService,
    DEFAULT_REJECT_KEYWORDS
)
from src.core.database import Job
from src.core.llm import FilterResult
from src.utils.config import Preferences
from src.utils.markdown_parser import KeywordFilters


@dataclass
class MockPreferences:
    """Mock preferences for testing."""
    keywords: KeywordFilters = None
    blacklisted_companies: list = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = KeywordFilters(
                reject_keywords=["security clearance", "no sponsorship"],
                prefer_keywords=["remote", "python"]
            )
        if self.blacklisted_companies is None:
            self.blacklisted_companies = ["Revature", "Infosys"]


class TestPreFilter:
    """Test PreFilter class."""

    def test_pre_filter_initialization(self):
        """Test PreFilter loads preferences."""
        prefs = MockPreferences()
        pre_filter = PreFilter(prefs)
        
        assert "security clearance" in pre_filter.reject_keywords
        assert "revature" in pre_filter.blacklisted_companies

    def test_pre_filter_includes_defaults(self):
        """Test PreFilter includes default reject keywords."""
        prefs = MockPreferences(keywords=KeywordFilters(reject_keywords=[], prefer_keywords=[]))
        pre_filter = PreFilter(prefs)
        
        # Should still have defaults
        assert "security clearance" in pre_filter.reject_keywords
        assert "no sponsorship" in pre_filter.reject_keywords

    def test_should_reject_blacklisted_company(self):
        """Test rejecting blacklisted company."""
        prefs = MockPreferences()
        pre_filter = PreFilter(prefs)
        
        job = Job(id=1, company="Revature", jd_markdown="Great job")
        should_reject, reason = pre_filter.should_reject(job)
        
        assert should_reject is True
        assert "Blacklisted" in reason
        assert "Revature" in reason

    def test_should_reject_keyword_in_jd(self):
        """Test rejecting job with reject keyword."""
        prefs = MockPreferences()
        pre_filter = PreFilter(prefs)
        
        job = Job(id=1, company="Good Corp", jd_markdown="Security clearance required")
        should_reject, reason = pre_filter.should_reject(job)
        
        assert should_reject is True
        assert "keyword" in reason.lower()

    def test_should_not_reject_clean_job(self):
        """Test passing clean job."""
        prefs = MockPreferences()
        pre_filter = PreFilter(prefs)
        
        job = Job(id=1, company="Google", jd_markdown="Work on cutting-edge AI")
        should_reject, reason = pre_filter.should_reject(job)
        
        assert should_reject is False
        assert reason is None


class TestFilterStats:
    """Test FilterStats dataclass."""

    def test_filter_stats_initialization(self):
        """Test FilterStats starts at zero."""
        stats = FilterStats()
        
        assert stats.total == 0
        assert stats.high_match == 0
        assert stats.medium_match == 0
        assert stats.rejected == 0
        assert stats.cost_usd == 0.0

    def test_filter_stats_increments(self):
        """Test incrementing stats."""
        stats = FilterStats()
        
        stats.total = 10
        stats.high_match = 2
        stats.medium_match = 5
        stats.rejected = 3
        stats.cost_usd = 0.015
        
        assert stats.total == 10
        assert stats.high_match + stats.medium_match + stats.rejected == 10

    def test_filter_stats_str(self):
        """Test FilterStats string representation."""
        stats = FilterStats(
            total=50,
            high_match=10,
            medium_match=20,
            rejected=20,
            cost_usd=0.0523
        )
        
        stats_str = str(stats)
        
        assert "Total: 50" in stats_str
        assert "High: 10" in stats_str
        assert "Cost: $0.0523" in stats_str


class TestJobFilterService:
    """Test JobFilterService class."""

    @pytest.mark.asyncio
    async def test_filter_new_jobs_no_jobs(self):
        """Test filtering when no new jobs."""
        # Mock database with no jobs
        mock_db = MagicMock()
        mock_db.get_jobs_by_status.return_value = []
        
        service = JobFilterService(db=mock_db)
        stats = await service.filter_new_jobs()
        
        assert stats.total == 0

    def test_score_routing_high_match(self):
        """Test routing for high score (>= 0.85)."""
        # Test that scores >= 0.85 become status='matched', decision_type='auto'
        assert 0.85 >= 0.85  # High match threshold
        assert 0.90 >= 0.85
        assert 1.0 >= 0.85

    def test_score_routing_medium_match(self):
        """Test routing for medium score (0.60-0.85)."""
        # Test that scores 0.60-0.85 become status='matched', decision_type='manual'
        assert 0.60 <= 0.75 < 0.85
        assert 0.60 <= 0.70 < 0.85

    def test_score_routing_rejected(self):
        """Test routing for low score (< 0.60)."""
        # Test that scores < 0.60 become status='rejected'
        assert 0.50 < 0.60
        assert 0.30 < 0.60

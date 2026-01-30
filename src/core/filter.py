"""Job filtering service using GLM for intelligent job scoring.

This module provides:
- PreFilter: Fast keyword/blacklist rejection before LLM
- JobFilterService: Main filtering orchestration with batch processing
- FilterStats: Statistics tracking for filtering runs
"""

import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from src.core.database import Database, Job
from src.core.llm import GLMClient, FilterResult
from src.utils.config import ConfigLoader, Preferences, Resume
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Default reject keywords for pre-filtering
DEFAULT_REJECT_KEYWORDS = [
    # Security clearance
    "security clearance",
    "clearance required",
    "secret clearance",
    "ts/sci",
    "top secret",
    
    # Citizenship requirements
    "us citizen only",
    "us citizens only",
    "must be a us citizen",
    "permanent resident required",
    
    # No sponsorship
    "no sponsorship",
    "not able to sponsor",
    "unable to sponsor",
    "must be authorized to work without sponsorship",
    "without visa sponsorship",
    "no visa sponsorship",
    "sponsorship not available",
    "cannot sponsor",
    "will not sponsor",
    
    # Staffing agency indicators
    "w2 through our vendor",
    "contract to hire",
    "corp to corp",
    "c2c position",
    "third party",
    "staffing agency",
]


class PreFilter:
    """Pre-filter jobs based on keywords and blacklists.
    
    Quick rejection before expensive LLM calls to save costs.
    """

    def __init__(self, preferences: Preferences):
        """Initialize pre-filter with user preferences.
        
        Args:
            preferences: User job preferences with blacklists and keywords
        """
        self.reject_keywords = [
            kw.lower() 
            for kw in (preferences.keywords.reject_keywords if preferences.keywords else [])
        ]
        # Add default keywords if not already present
        for default_kw in DEFAULT_REJECT_KEYWORDS:
            if default_kw not in self.reject_keywords:
                self.reject_keywords.append(default_kw)
        
        self.blacklisted_companies = [
            c.lower() 
            for c in preferences.blacklisted_companies
        ]
        
        logger.info(
            f"PreFilter initialized: {len(self.blacklisted_companies)} blacklisted companies, "
            f"{len(self.reject_keywords)} reject keywords"
        )

    def should_reject(self, job: Job) -> Tuple[bool, Optional[str]]:
        """Check if job should be rejected before LLM filtering.
        
        Args:
            job: Job to check
            
        Returns:
            Tuple of (should_reject: bool, reason: str or None)
        """
        # Check company blacklist
        if job.company and job.company.lower() in self.blacklisted_companies:
            return True, f"Blacklisted company: {job.company}"

        # Check reject keywords in job description
        jd_lower = (job.jd_markdown or "").lower()
        for keyword in self.reject_keywords:
            if keyword in jd_lower:
                return True, f"Reject keyword found: '{keyword}'"

        return False, None


@dataclass
class FilterStats:
    """Statistics from a filtering run.
    
    Attributes:
        total: Total jobs processed
        high_match: Jobs with score >= 0.85 (auto-apply)
        medium_match: Jobs with 0.60 <= score < 0.85 (manual review)
        rejected: Jobs with score < 0.60
        pre_filtered: Jobs rejected by pre-filter (didn't use LLM)
        errors: Jobs that failed to process
        cost_usd: Total cost in USD
    """
    total: int = 0
    high_match: int = 0       # >= 0.85
    medium_match: int = 0     # 0.60 - 0.85
    rejected: int = 0         # < 0.60
    pre_filtered: int = 0     # Rejected before LLM
    errors: int = 0
    cost_usd: float = 0.0
    
    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"Total: {self.total}, "
            f"High: {self.high_match}, "
            f"Medium: {self.medium_match}, "
            f"Rejected: {self.rejected}, "
            f"Pre-filtered: {self.pre_filtered}, "
            f"Errors: {self.errors}, "
            f"Cost: ${self.cost_usd:.4f}"
        )


class JobFilterService:
    """Service for filtering jobs using GLM.
    
    Orchestrates the complete filtering pipeline:
    1. Load jobs with status='new'
    2. Pre-filter (blacklist, keywords)
    3. LLM scoring with GLM
    4. Update database with results
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        glm_client: Optional[GLMClient] = None,
        config: Optional[ConfigLoader] = None
    ):
        """Initialize filter service.
        
        Args:
            db: Database instance (defaults to new Database())
            glm_client: GLM client (defaults to new GLMClient())
            config: Config loader (defaults to new ConfigLoader())
        """
        self.db = db or Database()
        self.glm = glm_client or GLMClient()
        self.config = config or ConfigLoader()
        
        # Load preferences for pre-filter
        preferences = self.config.get_preferences()
        self.pre_filter = PreFilter(preferences)
        
        logger.info("JobFilterService initialized")

    async def filter_new_jobs(
        self,
        batch_size: int = 10,
        limit: int = 100
    ) -> FilterStats:
        """Filter all new jobs.
        
        Args:
            batch_size: Number of jobs to process concurrently
            limit: Maximum number of jobs to process
            
        Returns:
            FilterStats with results summary
        """
        stats = FilterStats()
        
        # Get new jobs from database
        jobs = self.db.get_jobs_by_status("new", limit=limit)
        stats.total = len(jobs)
        
        if not jobs:
            logger.info("No new jobs to filter")
            return stats
        
        logger.info(f"Filtering {len(jobs)} new jobs (batch_size={batch_size})")
        
        # Load user profile
        resume = self.config.get_resume()
        preferences = self.config.get_preferences()
        
        # Build preference summary for prompt
        pref_summary = self._build_preference_summary(preferences)
        
        # Process jobs in batches
        for i in range(0, len(jobs), batch_size):
            batch = jobs[i:i + batch_size]
            
            # Process batch
            for job in batch:
                try:
                    await self._filter_single_job(job, resume, pref_summary, stats)
                except Exception as e:
                    logger.error(f"Failed to filter job {job.id} ({job.title}): {e}")
                    stats.errors += 1
            
            # Rate limiting between batches
            if i + batch_size < len(jobs):
                await asyncio.sleep(0.5)
        
        # Update stats with total cost
        stats.cost_usd = self.glm.total_cost
        
        logger.info(f"Filtering complete: {stats}")
        return stats

    async def _filter_single_job(
        self,
        job: Job,
        resume: Resume,
        pref_summary: str,
        stats: FilterStats
    ) -> None:
        """Filter a single job and update database.
        
        Args:
            job: Job to filter
            resume: User resume
            pref_summary: Formatted preferences summary
            stats: Stats object to update
        """
        # Pre-filter check
        should_reject, reason = self.pre_filter.should_reject(job)
        if should_reject:
            logger.debug(f"Pre-filtered job {job.id}: {reason}")
            
            # Update database as rejected
            self.db.update_job_status(job.id, "rejected")
            self.db.update_job_filter_results(
                job_id=job.id,
                score=0.0,
                reasoning=f"Pre-filter: {reason}",
                requirements=[],
                red_flags=[reason]
            )
            
            stats.pre_filtered += 1
            stats.rejected += 1
            return
        
        # LLM filtering
        try:
            result = await self.glm.filter_job(
                jd_markdown=job.jd_markdown or "",
                resume_summary=resume.summary,
                preferences=pref_summary
            )
        except Exception as e:
            logger.error(f"GLM filtering failed for job {job.id}: {e}")
            raise
        
        # Update database with results
        self._update_job_with_result(job, result, stats)

    def _update_job_with_result(
        self,
        job: Job,
        result: FilterResult,
        stats: FilterStats
    ) -> None:
        """Update job record with filter result.
        
        Args:
            job: Job being filtered
            result: FilterResult from GLM
            stats: Stats object to update
        """
        # Determine status and decision type based on score
        if result.score >= 0.85:
            status = "matched"
            decision_type = "auto"
            stats.high_match += 1
            logger.info(f"High match (score={result.score:.2f}): {job.title} at {job.company}")
        elif result.score >= 0.60:
            status = "matched"
            decision_type = "manual"
            stats.medium_match += 1
            logger.info(f"Medium match (score={result.score:.2f}): {job.title} at {job.company}")
        else:
            status = "rejected"
            decision_type = None
            stats.rejected += 1
            logger.debug(f"Rejected (score={result.score:.2f}): {job.title} at {job.company}")
        
        # Update database
        self.db.update_job_filter_results(
            job_id=job.id,
            score=result.score,
            reasoning=result.reasoning,
            requirements=result.key_requirements,
            red_flags=result.red_flags
        )
        
        self.db.update_job_status(
            job_id=job.id,
            status=status,
            decision_type=decision_type
        )

    def _build_preference_summary(self, preferences: Preferences) -> str:
        """Build formatted preference summary for prompts.
        
        Args:
            preferences: User preferences
            
        Returns:
            Formatted string for inclusion in prompts
        """
        lines = []
        
        # Target positions
        if preferences.target_positions:
            lines.append(f"Target Positions: {', '.join(preferences.target_positions)}")
        
        # Location
        if preferences.location:
            lines.append(f"Preferred Location: {preferences.location.preferred_location}")
            if preferences.location.remote_only:
                lines.append("Remote-only preferred: Yes")
        
        # Salary
        if preferences.salary:
            if preferences.salary.target_min:
                lines.append(f"Minimum Salary: ${preferences.salary.target_min:,}/year")
            if preferences.salary.target_max:
                lines.append(f"Target Salary: ${preferences.salary.target_max:,}/year")
        
        # Visa sponsorship
        if preferences.work_authorization:
            lines.append(f"Requires Visa Sponsorship: {preferences.work_authorization.needs_sponsorship}")
        
        # Preferred keywords
        if preferences.keywords and preferences.keywords.prefer_keywords:
            lines.append(f"Preferred Keywords: {', '.join(preferences.keywords.prefer_keywords)}")
        
        return "\n".join(lines) if lines else "No specific preferences"

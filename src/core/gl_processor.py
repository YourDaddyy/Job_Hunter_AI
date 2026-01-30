"""GLM Processor with Three-Tier Filtering System.

This module processes unfiltered jobs with GLM and implements a three-tier scoring system:
- Tier 1 (≥85): Auto-generate resume → Ready to apply
- Tier 2 (60-84): Add to campaign report → Awaiting user decision
- Tier 3 (<60): Keep in database → Archived, no action

Key features:
- Enhanced GLM prompts with achievements and preferences
- Semantic deduplication to avoid duplicate applications
- Automatic resume generation for Tier 1 jobs
- Batch processing with progress tracking
- Cost tracking and error handling
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from src.core.database import Database, Job
from src.core.llm import LLMFactory, BaseLLMClient
from src.core.tailor import ResumeTailoringService
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessorStats:
    """Statistics from a GL processing run.

    Attributes:
        total_processed: Total jobs processed
        tier1_high_match: Jobs with score ≥85 (auto-resume generated)
        tier2_medium_match: Jobs with score 60-84 (awaiting decision)
        tier3_low_match: Jobs with score <60 (archived)
        resumes_generated: Number of resumes successfully generated
        semantic_duplicates_found: Number of semantic duplicates detected
        errors: Number of jobs that failed to process
        cost_usd: Total API cost in USD
    """
    total_processed: int = 0
    tier1_high_match: int = 0      # ≥85, resumes generated
    tier2_medium_match: int = 0    # 60-84, awaiting decision
    tier3_low_match: int = 0       # <60, archived
    resumes_generated: int = 0
    semantic_duplicates_found: int = 0
    errors: int = 0
    cost_usd: float = 0.0

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"Total: {self.total_processed}, "
            f"Tier 1: {self.tier1_high_match}, "
            f"Tier 2: {self.tier2_medium_match}, "
            f"Tier 3: {self.tier3_low_match}, "
            f"Resumes: {self.resumes_generated}, "
            f"Duplicates: {self.semantic_duplicates_found}, "
            f"Errors: {self.errors}, "
            f"Cost: ${self.cost_usd:.4f}"
        )


class GLMProcessor:
    """Process unfiltered jobs with GLM three-tier filtering system.

    This processor:
    1. Queries all jobs where is_processed=FALSE
    2. For each job:
       - Loads achievements.md and preferences.md
       - Calls GLM to score 0-100
       - Updates database with ai_score, ai_reasoning
       - Sets is_processed=TRUE
    3. Implements three-tier system based on score
    4. Auto-generates resumes for Tier 1 jobs
    5. Checks for semantic duplicates
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        filter_client: Optional[BaseLLMClient] = None,
        tailor_client: Optional[BaseLLMClient] = None,
        tailor_service: Optional[ResumeTailoringService] = None,
        config: Optional[ConfigLoader] = None
    ):
        """Initialize GL processor.

        Args:
            db: Database instance
            filter_client: LLM client for filtering (defaults key "filter")
            tailor_client: LLM client for tailoring (defaults key "tailor")
            tailor_service: Resume tailoring service
            config: Config loader
        """
        self.config = config or ConfigLoader()
        self.db = db or Database()
        
        # Use Factory to get clients if not provided
        self.glm = filter_client or LLMFactory.create_client("filter", self.config)
        self.claude = tailor_client or LLMFactory.create_client("tailor", self.config)
        
        self.tailor = tailor_service or ResumeTailoringService(
            db=self.db,
            llm_client=self.claude,
            config=self.config
        )

        logger.info("GLMProcessor initialized")

    async def process_unfiltered_jobs(
        self,
        batch_size: int = 20,
        limit: Optional[int] = None,
        enable_semantic_dedup: bool = True,
        enable_tier1_resume: bool = True
    ) -> ProcessorStats:
        """Process all unfiltered jobs with three-tier system.

        Args:
            batch_size: Number of jobs to process in parallel
            limit: Maximum number of jobs to process (None = all)
            enable_semantic_dedup: Enable semantic duplicate detection
            enable_tier1_resume: Auto-generate resumes for Tier 1 jobs

        Returns:
            ProcessorStats with results summary
        """
        stats = ProcessorStats()

        # Query unprocessed jobs (is_processed=FALSE)
        unprocessed_jobs = self._get_unprocessed_jobs(limit)

        if not unprocessed_jobs:
            logger.info("No unprocessed jobs found")
            return stats

        logger.info(f"Processing {len(unprocessed_jobs)} unfiltered jobs")

        # Load user profile (achievements + preferences)
        achievements = self.config.get_achievements()
        preferences = self.config.get_preferences()

        # Format for prompt
        achievements_text = self._format_achievements(achievements)
        preferences_text = self._format_preferences(preferences)

        # Process jobs in batches
        for i in range(0, len(unprocessed_jobs), batch_size):
            batch = unprocessed_jobs[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(unprocessed_jobs) + batch_size - 1) // batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")

            # Process batch concurrently
            tasks = [
                self._process_single_job(
                    job,
                    achievements_text,
                    preferences_text,
                    stats,
                    enable_semantic_dedup,
                    enable_tier1_resume,
                    job_num=i + idx + 1,
                    total_jobs=len(unprocessed_jobs)
                )
                for idx, job in enumerate(batch)
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            # Rate limiting between batches
            if i + batch_size < len(unprocessed_jobs):
                await asyncio.sleep(1.0)

        # Update total cost
        stats.cost_usd = self.glm.total_cost + self.claude.total_cost

        logger.info(f"Processing complete: {stats}")
        return stats

    async def _process_single_job(
        self,
        job: Job,
        achievements_text: str,
        preferences_text: str,
        stats: ProcessorStats,
        enable_semantic_dedup: bool,
        enable_tier1_resume: bool,
        job_num: int,
        total_jobs: int
    ) -> None:
        """Process a single job through the three-tier system.

        Args:
            job: Job to process
            achievements_text: Formatted achievements
            preferences_text: Formatted preferences
            stats: Stats object to update
            enable_semantic_dedup: Enable semantic duplicate check
            enable_tier1_resume: Auto-generate resume for Tier 1
            job_num: Current job number for progress tracking
            total_jobs: Total number of jobs
        """
        try:
            logger.info(
                f"[{job_num}/{total_jobs}] Processing: {job.title} @ {job.company}"
            )

            # Check for semantic duplicates (same company)
            if enable_semantic_dedup:
                is_duplicate, similar_job_id = await self._check_semantic_duplicate(
                    job
                )
                if is_duplicate:
                    logger.info(
                        f"Semantic duplicate detected: Job {job.id} similar to Job {similar_job_id}"
                    )
                    self._mark_as_duplicate(job.id, similar_job_id)
                    stats.semantic_duplicates_found += 1
                    stats.total_processed += 1
                    return

            # Call GLM with enhanced prompt
            score, reasoning, tier = await self._score_job_with_glm(
                job,
                achievements_text,
                preferences_text
            )

            # Update database with results
            self._update_job_with_score(job.id, score, reasoning)

            # Handle based on tier
            if tier == "high":
                # Tier 1: Auto-generate resume
                stats.tier1_high_match += 1

                if enable_tier1_resume:
                    resume_generated = await self._generate_resume_for_tier1(job)
                    if resume_generated:
                        stats.resumes_generated += 1
                        logger.info(
                            f"[{job_num}/{total_jobs}] Tier 1 (score={score}): "
                            f"Resume generated for {job.title}"
                        )
                    else:
                        logger.warning(
                            f"[{job_num}/{total_jobs}] Tier 1 (score={score}): "
                            f"Resume generation failed for {job.title}"
                        )
                else:
                    logger.info(
                        f"[{job_num}/{total_jobs}] Tier 1 (score={score}): "
                        f"{job.title} (resume generation disabled)"
                    )

            elif tier == "medium":
                # Tier 2: Add to campaign report
                stats.tier2_medium_match += 1
                logger.info(
                    f"[{job_num}/{total_jobs}] Tier 2 (score={score}): "
                    f"{job.title} → Awaiting user decision"
                )

            else:
                # Tier 3: Archive
                stats.tier3_low_match += 1
                logger.debug(
                    f"[{job_num}/{total_jobs}] Tier 3 (score={score}): "
                    f"{job.title} → Archived"
                )

            stats.total_processed += 1

        except Exception as e:
            logger.error(
                f"[{job_num}/{total_jobs}] Failed to process job {job.id} "
                f"({job.title}): {e}",
                exc_info=True
            )
            stats.errors += 1

    async def _score_job_with_glm(
        self,
        job: Job,
        achievements_text: str,
        preferences_text: str
    ) -> Tuple[int, str, str]:
        """Score job using GLM with enhanced prompt.

        Args:
            job: Job to score
            achievements_text: Formatted achievements
            preferences_text: Formatted preferences

        Returns:
            Tuple of (score: int, reasoning: str, tier: str)
            - score: 0-100
            - reasoning: Explanation of score
            - tier: "high" (≥85), "medium" (60-84), or "low" (<60)
        """
        prompt = self._build_enhanced_glm_prompt(
            job,
            achievements_text,
            preferences_text
        )

        messages = [{"role": "user", "content": prompt}]

        response = await self.glm.chat(messages, temperature=0.3, max_tokens=800)

        # Parse JSON response
        # Parse JSON response
        data = self.glm.parse_json_response(response.content)

        score = int(data.get("score", 0))
        reasoning = data.get("reasoning", "No reasoning provided")
        tier = data.get("tier", "low")

        return score, reasoning, tier

    def _build_enhanced_glm_prompt(
        self,
        job: Job,
        achievements_text: str,
        preferences_text: str
    ) -> str:
        """Build enhanced GLM prompt with achievements and preferences.

        Args:
            job: Job to analyze
            achievements_text: Formatted achievements
            preferences_text: Formatted preferences

        Returns:
            Formatted prompt string
        """
        # Extract job data
        title = job.title
        company = job.company
        location = job.location or "Not specified"
        salary = self._format_salary(job)
        description = job.jd_markdown or job.jd_raw or "No description available"
        source = job.platform

        return f"""You are a job filtering AI analyzing jobs for this candidate.

# CANDIDATE ACHIEVEMENTS
{achievements_text}

# CANDIDATE PREFERENCES/REQUIREMENTS
{preferences_text}

# JOB TO ANALYZE
Title: {title}
Company: {company}
Location: {location}
Salary: {salary}
Description:
{description}
Source: {source}

# YOUR TASK
Score this job 0-100 based on:

## Match Criteria (0-100 points)
- Skills match with achievements (0-40 points)
- Experience level match (0-20 points)
- Tech stack alignment (0-15 points)
- Remote work availability (0-10 points)
- Salary range (0-10 points)
- Visa sponsorship if needed (0-5 points)

## Red Flags (Subtract points)
- On-site required when remote needed (-20)
- No visa sponsorship when needed (-15)
- Salary below minimum (-10)
- Staffing agency/contract-to-hire (-10)
- Skills completely mismatched (-20)

Return JSON:
{{
    "score": 85,
    "reasoning": "Strong match: Python, ML, remote available...",
    "red_flags": [],
    "key_matches": ["Python", "ML", "Remote"],
    "tier": "high"
}}

SCORE GUIDELINES:
- 85-100: Excellent match (Tier 1 - auto-resume) → tier: "high"
- 60-84: Good match (Tier 2 - user review) → tier: "medium"
- 0-59: Poor match (Tier 3 - archive) → tier: "low"

Return ONLY valid JSON, no markdown or extra text."""

    async def _check_semantic_duplicate(
        self,
        new_job: Job
    ) -> Tuple[bool, Optional[int]]:
        """Check if job is semantically similar to existing jobs at same company.

        Uses simple heuristics to detect duplicates like:
        - "AI Engineer" vs "Artificial Intelligence Engineer"
        - "ML Engineer" vs "Machine Learning Engineer"

        Args:
            new_job: Job to check

        Returns:
            Tuple of (is_duplicate: bool, similar_job_id: Optional[int])
        """
        # Get existing jobs from the same company
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, title, jd_markdown
            FROM jobs
            WHERE company = ?
            AND id != ?
            AND status != 'rejected'
            LIMIT 10
        """, (new_job.company, new_job.id))

        existing_jobs = cursor.fetchall()

        if not existing_jobs:
            return False, None

        # Simple semantic check using title similarity
        new_title_lower = new_job.title.lower()
        new_title_normalized = self._normalize_title(new_title_lower)

        for existing_job in existing_jobs:
            existing_title_lower = existing_job['title'].lower()
            existing_title_normalized = self._normalize_title(existing_title_lower)

            # Check if titles are semantically similar
            if self._are_titles_similar(
                new_title_normalized,
                existing_title_normalized
            ):
                logger.debug(
                    f"Semantic match: '{new_job.title}' ~ '{existing_job['title']}'"
                )
                return True, existing_job['id']

        return False, None

    def _normalize_title(self, title: str) -> str:
        """Normalize job title for comparison.

        Args:
            title: Job title

        Returns:
            Normalized title
        """
        # Common abbreviations and expansions
        replacements = {
            "artificial intelligence": "ai",
            "machine learning": "ml",
            "software development engineer in test": "sdet",
            "quality assurance": "qa",
            "full stack": "fullstack",
            "full-stack": "fullstack",
            "backend": "back-end",
            "frontend": "front-end",
        }

        title_normalized = title.lower()
        for old, new in replacements.items():
            title_normalized = title_normalized.replace(old, new)

        # Remove common words
        common_words = ["senior", "junior", "lead", "principal", "staff", "the", "a", "an"]
        words = title_normalized.split()
        words = [w for w in words if w not in common_words]

        return " ".join(words)

    def _are_titles_similar(self, title1: str, title2: str) -> bool:
        """Check if two normalized titles are similar.

        Args:
            title1: First normalized title
            title2: Second normalized title

        Returns:
            True if similar, False otherwise
        """
        # Exact match
        if title1 == title2:
            return True

        # Check if one is substring of other
        if title1 in title2 or title2 in title1:
            return True

        # Check word overlap (at least 80% of words match)
        words1 = set(title1.split())
        words2 = set(title2.split())

        if not words1 or not words2:
            return False

        overlap = len(words1 & words2)
        min_words = min(len(words1), len(words2))

        return overlap >= 0.8 * min_words

    async def _generate_resume_for_tier1(self, job: Job) -> bool:
        """Generate tailored resume for Tier 1 job.

        Args:
            job: Job to generate resume for

        Returns:
            True if resume generated successfully, False otherwise
        """
        try:
            result = await self.tailor.tailor_resume_for_job(
                job_id=job.id,
                template="modern"
            )

            logger.info(
                f"Resume generated for job {job.id}: {result.pdf_path} "
                f"(cost: ${result.cost_usd:.4f})"
            )

            # Mark job as ready_to_apply
            self.db.update_job_status(job.id, "matched", decision_type="auto")

            return True

        except Exception as e:
            logger.error(f"Failed to generate resume for job {job.id}: {e}")
            return False

    def _update_job_with_score(
        self,
        job_id: int,
        score: int,
        reasoning: str
    ) -> None:
        """Update job with score and mark as processed.

        Args:
            job_id: Job ID
            score: Score (0-100)
            reasoning: Reasoning for score
        """
        # Convert score to 0-1 scale for match_score
        match_score = score / 100.0

        # Determine status based on tier
        if score >= 85:
            status = "matched"
            decision_type = "auto"
        elif score >= 60:
            status = "matched"
            decision_type = "manual"
        else:
            status = "rejected"
            decision_type = None

        # Update database
        self.db.update_job_filter_results(
            job_id=job_id,
            score=match_score,
            reasoning=reasoning,
            requirements=[],  # Extracted from reasoning if needed
            red_flags=[]  # Extracted from reasoning if needed
        )

        self.db.update_job_status(job_id, status, decision_type)

        # Mark as processed
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET is_processed = 1
            WHERE id = ?
        """, (job_id,))
        self.db.conn.commit()

    def _mark_as_duplicate(self, job_id: int, similar_job_id: int) -> None:
        """Mark job as duplicate.

        Args:
            job_id: Job ID to mark as duplicate
            similar_job_id: ID of similar job
        """
        self.db.update_job_status(job_id, "rejected", decision_type=None)
        self.db.update_job_filter_results(
            job_id=job_id,
            score=0.0,
            reasoning=f"Semantic duplicate of job #{similar_job_id}",
            requirements=[],
            red_flags=["Duplicate job posting"]
        )

        # Mark as processed
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET is_processed = 1
            WHERE id = ?
        """, (job_id,))
        self.db.conn.commit()

    def _get_unprocessed_jobs(self, limit: Optional[int]) -> List[Job]:
        """Get all unprocessed jobs from database.

        Args:
            limit: Maximum number of jobs to retrieve

        Returns:
            List of Job objects
        """
        cursor = self.db.conn.cursor()

        if limit:
            cursor.execute("""
                SELECT * FROM jobs
                WHERE is_processed = 0
                ORDER BY scraped_at DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT * FROM jobs
                WHERE is_processed = 0
                ORDER BY scraped_at DESC
            """)

        rows = cursor.fetchall()
        return [self.db._row_to_job(row) for row in rows]

    def _format_achievements(self, achievements) -> str:
        """Format achievements for prompt.

        Args:
            achievements: Achievements dataclass

        Returns:
            Formatted string
        """
        lines = []

        for achievement in achievements.items:
            lines.append(f"## {achievement.name}")
            if achievement.category:
                lines.append(f"Category: {achievement.category}")
            if achievement.keywords:
                lines.append(f"Keywords: {', '.join(achievement.keywords)}")
            if achievement.bullets:
                for bullet in achievement.bullets:
                    lines.append(f"- {bullet}")
            lines.append("")

        return "\n".join(lines)

    def _format_preferences(self, preferences) -> str:
        """Format preferences for prompt.

        Args:
            preferences: Preferences dataclass

        Returns:
            Formatted string
        """
        lines = []

        # Target positions
        if preferences.target_positions:
            lines.append(f"Target Positions: {', '.join(preferences.target_positions)}")

        # Location
        if preferences.location:
            if preferences.location.preferred:
                lines.append(f"Preferred Location: {', '.join(preferences.location.preferred)}")

        # Salary
        if preferences.salary:
            lines.append(f"Minimum Salary: ${preferences.salary.minimum:,} {preferences.salary.currency}")
            if preferences.salary.target_min:
                lines.append(f"Target Salary: ${preferences.salary.target_min:,} {preferences.salary.currency}")

        # Work authorization
        if hasattr(preferences, 'visa_sponsorship_required'):
            lines.append(f"Visa Sponsorship Required: {preferences.visa_sponsorship_required}")

        return "\n".join(lines)

    def _format_salary(self, job: Job) -> str:
        """Format salary range for display.

        Args:
            job: Job object

        Returns:
            Formatted salary string
        """
        if job.salary_min and job.salary_max:
            return f"${job.salary_min//1000}k-${job.salary_max//1000}k {job.salary_currency}"
        elif job.salary_min:
            return f"${job.salary_min//1000}k+ {job.salary_currency}"
        elif job.salary_max:
            return f"Up to ${job.salary_max//1000}k {job.salary_currency}"
        else:
            return "Not specified"

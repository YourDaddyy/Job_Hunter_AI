#!/usr/bin/env python3
"""Test script for GLM Processor.

Tests the three-tier job filtering system:
1. Queries jobs where is_processed=FALSE
2. Loads achievements.md and preferences.md
3. Calls GLM to score each job 0-100
4. Implements three tiers:
   - â‰?5: Generate resume (Tier 1)
   - 60-84: Add to report (Tier 2)
   - <60: Archive (Tier 3)
5. Updates database with ai_score, ai_reasoning, is_processed=TRUE
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.gl_processor import GLMProcessor
from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_gl_processor():
    """Test GLM processor with sample unprocessed jobs."""

    logger.info("=" * 80)
    logger.info("GLM Processor Test")
    logger.info("=" * 80)

    # Initialize processor
    db = Database()
    processor = GLMProcessor(db=db)

    # Check for unprocessed jobs
    logger.info("Checking for unprocessed jobs...")
    unprocessed_jobs = processor._get_unprocessed_jobs(limit=None)
    logger.info(f"Found {len(unprocessed_jobs)} unprocessed jobs")

    if not unprocessed_jobs:
        logger.warning("No unprocessed jobs found in database")
        logger.info("To test with real jobs, first import jobs using:")
        logger.info("  - scripts/test_importer.py")
        logger.info("  - MCP tool: import_antigravity_results")
        return

    # Show sample job
    if unprocessed_jobs:
        sample = unprocessed_jobs[0]
        logger.info(f"\nSample unprocessed job:")
        logger.info(f"  ID: {sample.id}")
        logger.info(f"  Title: {sample.title}")
        logger.info(f"  Company: {sample.company}")
        logger.info(f"  Platform: {sample.platform}")
        logger.info(f"  URL: {sample.url[:60]}...")

    # Run processor with small batch
    logger.info("\n" + "=" * 80)
    logger.info("Running GLM Processor (limit=5 for testing)...")
    logger.info("=" * 80)

    try:
        stats = await processor.process_unfiltered_jobs(
            batch_size=5,
            limit=5,
            enable_semantic_dedup=True,
            enable_tier1_resume=False  # Disable resume generation for testing
        )

        # Print results
        logger.info("\n" + "=" * 80)
        logger.info("Processing Results:")
        logger.info("=" * 80)
        logger.info(f"Total Processed: {stats.total_processed}")
        logger.info(f"Tier 1 (â‰?5): {stats.tier1_high_match}")
        logger.info(f"Tier 2 (60-84): {stats.tier2_medium_match}")
        logger.info(f"Tier 3 (<60): {stats.tier3_low_match}")
        logger.info(f"Resumes Generated: {stats.resumes_generated}")
        logger.info(f"Semantic Duplicates: {stats.semantic_duplicates_found}")
        logger.info(f"Errors: {stats.errors}")
        logger.info(f"Cost (USD): ${stats.cost_usd:.4f}")
        logger.info("=" * 80)

        # Verify database updates
        logger.info("\nVerifying database updates...")
        cursor = db.conn.cursor()

        # Check for processed jobs
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE is_processed = 1
        """)
        result = cursor.fetchone()
        processed_count = result['count'] if result else 0
        logger.info(f"Jobs marked as processed: {processed_count}")

        # Show sample of processed jobs
        cursor.execute("""
            SELECT id, title, company, match_score, match_reasoning
            FROM jobs
            WHERE is_processed = 1
            LIMIT 3
        """)
        processed_samples = cursor.fetchall()

        if processed_samples:
            logger.info("\nSample processed jobs:")
            for job in processed_samples:
                score = job['match_score']
                tier = "Tier 1" if score >= 0.85 else "Tier 2" if score >= 0.60 else "Tier 3"
                logger.info(f"  Job {job['id']}: {job['title']} @ {job['company']}")
                logger.info(f"    Score: {score:.2f} ({tier})")
                logger.info(f"    Reasoning: {job['match_reasoning'][:80]}...")

        return stats

    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        raise


async def test_processor_with_mock_data():
    """Test processor with minimal mock setup."""
    logger.info("\nTesting processor initialization and helper methods...")

    processor = GLMProcessor()

    # Test achievement formatting
    logger.info("\nTesting achievement formatting...")
    try:
        achievements = processor.config.get_achievements()
        achievements_text = processor._format_achievements(achievements)
        logger.info(f"Achievements formatted: {len(achievements_text)} characters")
    except Exception as e:
        logger.warning(f"Could not test achievements: {e}")

    # Test preference formatting
    logger.info("\nTesting preference formatting...")
    try:
        preferences = processor.config.get_preferences()
        preferences_text = processor._format_preferences(preferences)
        logger.info(f"Preferences formatted: {len(preferences_text)} characters")
    except Exception as e:
        logger.warning(f"Could not test preferences: {e}")

    # Test title normalization
    logger.info("\nTesting title normalization...")
    test_titles = [
        "AI Engineer",
        "Artificial Intelligence Engineer",
        "Machine Learning Engineer",
        "ML Engineer",
        "Senior AI Engineer",
        "Full-Stack Engineer"
    ]

    for title in test_titles:
        normalized = processor._normalize_title(title.lower())
        logger.info(f"  '{title}' -> '{normalized}'")

    # Test title similarity
    logger.info("\nTesting title similarity...")
    title_pairs = [
        ("AI Engineer", "Artificial Intelligence Engineer"),
        ("ML Engineer", "Machine Learning Engineer"),
        ("Backend Engineer", "Frontend Engineer"),
        ("Senior Python Developer", "Python Developer")
    ]

    for t1, t2 in title_pairs:
        n1 = processor._normalize_title(t1.lower())
        n2 = processor._normalize_title(t2.lower())
        similar = processor._are_titles_similar(n1, n2)
        logger.info(f"  '{t1}' <-> '{t2}': {similar}")


def main():
    """Run all tests."""
    logger.info("Starting GLM Processor Tests\n")

    # Test initialization and helpers
    asyncio.run(test_processor_with_mock_data())

    logger.info("\n" + "=" * 80)
    logger.info("Running main processor test with database...")
    logger.info("=" * 80 + "\n")

    # Run main test
    try:
        stats = asyncio.run(test_gl_processor())

        logger.info("\n" + "=" * 80)
        logger.info("Test Summary")
        logger.info("=" * 80)

        if stats.total_processed == 0:
            logger.warning("No jobs were processed. Check database for unprocessed jobs.")
        else:
            logger.info("GLM Processor test completed successfully!")
            logger.info(f"Processed {stats.total_processed} jobs")
            logger.info(f"Distribution: T1={stats.tier1_high_match}, T2={stats.tier2_medium_match}, T3={stats.tier3_low_match}")

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

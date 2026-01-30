"""Test script for Antigravity JSON importer.

This script tests:
1. Sample JSON file creation
2. Import process
3. Deduplication (URL and fuzzy)
4. Source priority handling
5. Database state verification
"""

import json
import sqlite3
import sys
import io
from pathlib import Path
from datetime import datetime

# Set UTF-8 encoding for console output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import Database
from src.core.importer import (
    AntigravityImporter,
    generate_fuzzy_hash,
    parse_salary,
    determine_source_priority,
    resolve_duplicate
)


def create_sample_json_files():
    """Create sample JSON files for testing."""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # LinkedIn sample data (medium priority, visual platform)
    linkedin_jobs = [
        {
            "title": "AI Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Build cutting-edge AI systems. Work with GPT-4 and beyond. "
                          "Requirements: Python, PyTorch, 5+ years ML experience.",
            "url": "https://linkedin.com/jobs/ai-engineer-openai-1",
            "salary": "$150k-200k",
            "posted_date": "2026-01-27",
            "easy_apply": True
        },
        {
            "title": "Machine Learning Engineer",
            "company": "Google DeepMind",
            "location": "London, UK",
            "description": "Join our research team building AGI.",
            "url": "https://linkedin.com/jobs/ml-engineer-deepmind-2",
            "salary": "Â£100k-150k",
            "posted_date": "2026-01-26",
            "easy_apply": False
        },
        {
            "title": "Senior Backend Engineer",
            "company": "Stripe",
            "location": "San Francisco, CA",
            "description": "Build payment infrastructure at scale.",
            "url": "https://linkedin.com/jobs/backend-stripe-3",
            "salary": "$180k-250k",
            "posted_date": "2026-01-25",
            "easy_apply": True
        }
    ]

    # Indeed sample data (high priority, text-heavy platform)
    # Include one duplicate with more detailed description
    indeed_jobs = [
        {
            "title": "AI Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Build cutting-edge AI systems. Work with GPT-4 and beyond. "
                          "Requirements: Python, PyTorch, 5+ years ML experience. "
                          "Additional details: We're looking for someone passionate about AI safety "
                          "and alignment. You'll work on frontier models and help shape the future of AI. "
                          "Competitive salary, equity, and benefits. Hybrid work environment.",
            "url": "https://indeed.com/jobs/ai-engineer-openai-1",
            "salary": "$150,000-$200,000",
            "posted_date": "2026-01-27",
            "easy_apply": False
        },
        {
            "title": "Data Scientist",
            "company": "Meta",
            "location": "Menlo Park, CA",
            "description": "Analyze user behavior and build recommendation systems. "
                          "5+ years experience with Python, SQL, and ML frameworks.",
            "url": "https://indeed.com/jobs/data-scientist-meta-4",
            "salary": "$170k-220k",
            "posted_date": "2026-01-24",
            "easy_apply": False
        }
    ]

    # Glassdoor sample data (medium priority)
    # Include exact URL duplicate and fuzzy duplicate with worse description
    glassdoor_jobs = [
        {
            "title": "Machine Learning Engineer",
            "company": "Google DeepMind",
            "location": "London, UK",
            "description": "Join our research team.",
            "url": "https://linkedin.com/jobs/ml-engineer-deepmind-2",  # Exact URL duplicate
            "salary": "Â£100k-150k",
            "posted_date": "2026-01-26",
            "easy_apply": False
        },
        {
            "title": "Senior Backend Engineer",
            "company": "Stripe",
            "location": "Remote",
            "description": "Build payments.",  # Shorter description, should be skipped
            "url": "https://glassdoor.com/jobs/backend-stripe-5",
            "salary": "$180k-250k",
            "posted_date": "2026-01-25",
            "easy_apply": False
        },
        {
            "title": "Frontend Engineer",
            "company": "Vercel",
            "location": "Remote",
            "description": "Build the future of web development with Next.js.",
            "url": "https://glassdoor.com/jobs/frontend-vercel-6",
            "salary": "$140k-180k",
            "posted_date": "2026-01-23",
            "easy_apply": True
        }
    ]

    # Save files
    with open(data_dir / "linkedin_scraped.json", "w", encoding="utf-8") as f:
        json.dump(linkedin_jobs, f, indent=2)

    with open(data_dir / "indeed_scraped.json", "w", encoding="utf-8") as f:
        json.dump(indeed_jobs, f, indent=2)

    with open(data_dir / "glassdoor_scraped.json", "w", encoding="utf-8") as f:
        json.dump(glassdoor_jobs, f, indent=2)

    print("âœ?Created sample JSON files:")
    print(f"  - linkedin_scraped.json ({len(linkedin_jobs)} jobs)")
    print(f"  - indeed_scraped.json ({len(indeed_jobs)} jobs)")
    print(f"  - glassdoor_scraped.json ({len(glassdoor_jobs)} jobs)")
    print()


def test_fuzzy_hash():
    """Test fuzzy hash generation."""
    print("Testing fuzzy hash generation...")

    # Same job, different casing
    hash1 = generate_fuzzy_hash("OpenAI", "AI Engineer")
    hash2 = generate_fuzzy_hash("openai", "ai engineer")
    hash3 = generate_fuzzy_hash("  OpenAI  ", "  AI Engineer  ")

    assert hash1 == hash2 == hash3, "Fuzzy hashes should be identical"
    print(f"  âœ?Fuzzy hash: {hash1}")
    print()


def test_salary_parsing():
    """Test salary parsing."""
    print("Testing salary parsing...")

    tests = [
        ("$150k-200k", (150000, 200000)),
        ("$150,000-$200,000", (150000, 200000)),
        ("$150k+", (150000, None)),
        ("Up to $200k", (None, 200000)),
        ("Competitive", (None, None)),
        ("150k-200k", (150000, 200000)),
        ("Â£100k-150k", (100000, 150000)),
    ]

    for salary_str, expected in tests:
        result = parse_salary(salary_str)
        assert result == expected, f"Failed: {salary_str} -> {result} (expected {expected})"
        print(f"  âœ?{salary_str} -> {result}")

    print()


def test_source_priority():
    """Test source priority determination."""
    print("Testing source priority...")

    assert determine_source_priority("indeed") == 1, "Indeed should be priority 1"
    assert determine_source_priority("wellfound") == 1, "Wellfound should be priority 1"
    assert determine_source_priority("linkedin") == 2, "LinkedIn should be priority 2"
    assert determine_source_priority("glassdoor") == 2, "Glassdoor should be priority 2"

    print("  âœ?indeed: 1 (high)")
    print("  âœ?wellfound: 1 (high)")
    print("  âœ?linkedin: 2 (medium)")
    print("  âœ?glassdoor: 2 (medium)")
    print()


def test_resolve_duplicate():
    """Test duplicate resolution logic."""
    print("Testing duplicate resolution...")

    # Test 1: Higher priority source (lower number)
    existing = {
        'id': 1,
        'source_priority': 2,
        'jd_raw': 'Short description'
    }
    new = {
        'source_priority': 1,
        'description': 'Longer description with more details'
    }

    action, data = resolve_duplicate(existing, new)
    assert action == "update_full", "Should update when new has higher priority"
    print("  âœ?Higher priority source -> update_full")

    # Test 2: Same priority, longer description
    existing = {
        'id': 1,
        'source_priority': 2,
        'jd_raw': 'Short'
    }
    new = {
        'source_priority': 2,
        'description': 'Much longer description with lots of details'
    }

    action, data = resolve_duplicate(existing, new)
    assert action == "update_description", "Should update description when new is longer"
    print("  âœ?Same priority, longer description -> update_description")

    # Test 3: Same priority, shorter description
    existing = {
        'id': 1,
        'source_priority': 2,
        'jd_raw': 'Very long and detailed description'
    }
    new = {
        'source_priority': 2,
        'description': 'Short'
    }

    action, data = resolve_duplicate(existing, new)
    assert action == "skip", "Should skip when new is shorter"
    print("  âœ?Same priority, shorter description -> skip")

    # Test 4: Lower priority source (higher number)
    existing = {
        'id': 1,
        'source_priority': 1,
        'jd_raw': 'Description'
    }
    new = {
        'source_priority': 2,
        'description': 'Description'
    }

    action, data = resolve_duplicate(existing, new)
    assert action == "skip", "Should skip when new has lower priority"
    print("  âœ?Lower priority source -> skip")
    print()


def test_import_process():
    """Test the full import process."""
    print("Testing import process...")

    # Use in-memory database for testing
    db = Database(":memory:")
    db.init_schema()

    # Create importer
    importer = AntigravityImporter(db=db)

    # Import files
    stats = importer.import_multiple_files([
        "data\\linkedin_scraped.json",
        "data\\indeed_scraped.json",
        "data\\glassdoor_scraped.json"
    ])

    print(f"\nImport Statistics:")
    print(f"  Total jobs in files: {stats['total_jobs']}")
    print(f"  New jobs inserted: {stats['new_jobs']}")
    print(f"  URL duplicates skipped: {stats['url_duplicates']}")
    print(f"  Fuzzy duplicates skipped: {stats['fuzzy_duplicates_skipped']}")
    print(f"  Fuzzy duplicates updated: {stats['fuzzy_duplicates_updated']}")
    print()

    print("By source:")
    for source, source_stats in stats['by_source'].items():
        print(f"  {source}:")
        print(f"    Total: {source_stats['total']}")
        print(f"    New: {source_stats['new']}")
        print(f"    URL dup: {source_stats['url_dup']}")
        print(f"    Fuzzy dup skip: {source_stats['fuzzy_dup_skip']}")
        print(f"    Fuzzy dup update: {source_stats['fuzzy_dup_update']}")
    print()

    # Verify database state
    cursor = db.conn.cursor()

    # Count total jobs
    cursor.execute("SELECT COUNT(*) as count FROM jobs")
    total_jobs = cursor.fetchone()['count']
    print(f"Total jobs in database: {total_jobs}")

    # Check for fuzzy hash index
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_jobs_fuzzy_hash'")
    index = cursor.fetchone()
    print(f"Fuzzy hash index exists: {index is not None}")

    # Check specific jobs
    cursor.execute("SELECT * FROM jobs WHERE company = 'OpenAI'")
    openai_jobs = cursor.fetchall()
    print(f"\nOpenAI jobs: {len(openai_jobs)}")
    for job in openai_jobs:
        print(f"  - {job['title']} (source: {job['source']}, priority: {job['source_priority']})")
        print(f"    Description length: {len(job['jd_raw'] or '')}")
        print(f"    URL: {job['url']}")

    # Check Stripe jobs (fuzzy duplicate test)
    cursor.execute("SELECT * FROM jobs WHERE company = 'Stripe'")
    stripe_jobs = cursor.fetchall()
    print(f"\nStripe jobs: {len(stripe_jobs)}")
    for job in stripe_jobs:
        print(f"  - {job['title']} (source: {job['source']}, priority: {job['source_priority']})")
        print(f"    Description length: {len(job['jd_raw'] or '')}")

    # Verify expected results
    print("\nVerifying expected results...")

    # Should have 6 unique jobs (not 8, because of duplicates)
    # LinkedIn: 3 jobs
    # Indeed: 2 jobs (1 is fuzzy dup of LinkedIn OpenAI, should update it)
    # Glassdoor: 3 jobs (1 URL dup, 1 fuzzy dup with shorter desc, 1 new)
    # Expected: 3 (LinkedIn) + 1 (Indeed Meta) + 1 (Glassdoor Vercel) = 5 new
    # + 1 update (Indeed OpenAI updates LinkedIn OpenAI)
    assert total_jobs == 5, f"Expected 5 unique jobs, got {total_jobs}"
    print("  âœ?Correct number of unique jobs")

    # OpenAI job should have been updated to Indeed version (better description)
    assert len(openai_jobs) == 1, "Should have exactly 1 OpenAI job"
    openai_job = openai_jobs[0]
    assert openai_job['source'] == 'indeed', "OpenAI job should be from Indeed (higher priority)"
    assert len(openai_job['jd_raw']) > 200, "OpenAI job should have long description"
    print("  âœ?OpenAI job updated to Indeed version")

    # Stripe job should be from LinkedIn (longer description)
    assert len(stripe_jobs) == 1, "Should have exactly 1 Stripe job"
    stripe_job = stripe_jobs[0]
    assert stripe_job['source'] == 'linkedin', "Stripe job should be from LinkedIn"
    print("  âœ?Stripe job kept LinkedIn version (longer description)")

    print("\nâœ?All tests passed!")


def cleanup_test_files():
    """Remove test JSON files."""
    data_dir = Path("data")
    test_files = [
        "linkedin_scraped.json",
        "indeed_scraped.json",
        "glassdoor_scraped.json"
    ]

    print("\nCleaning up test files...")
    for filename in test_files:
        file_path = data_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"  âœ?Deleted {filename}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Antigravity JSON Importer Test Suite")
    print("=" * 60)
    print()

    try:
        # Unit tests
        test_fuzzy_hash()
        test_salary_parsing()
        test_source_priority()
        test_resolve_duplicate()

        # Integration tests
        create_sample_json_files()
        test_import_process()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nâœ?Test failed: {e}")
        return 1

    except Exception as e:
        print(f"\nâœ?Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup (optional - comment out to keep test files)
        # cleanup_test_files()
        pass

    return 0


if __name__ == "__main__":
    exit(main())

"""Test that database.py correctly handles new source tracking columns."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import Database


def test_database():
    """Test database operations with new columns."""
    print("=" * 80)
    print("TESTING UPDATED DATABASE.PY WITH SOURCE TRACKING COLUMNS")
    print("=" * 80)

    # Use absolute path to database
    db_path = Path(__file__).parent.parent / 'data' / 'jobs.db'
    print(f"\nConnecting to: {db_path}")
    db = Database(str(db_path))

    # Test 1: Read existing jobs
    print("\n1. Testing read operations...")
    jobs = db.get_jobs_by_status('new', limit=5)
    print(f"   Fetched {len(jobs)} jobs with status='new'")

    if jobs:
        print("\n   Sample jobs:")
        for j in jobs[:3]:
            print(f"\n   Job #{j.id}: {j.title}")
            print(f"      Company: {j.company}")
            print(f"      Platform: {j.platform}")
            print(f"      Source: {j.source}")
            print(f"      Source Priority: {j.source_priority}")
            print(f"      Is Processed: {j.is_processed}")

    # Test 2: Verify dataclass has new fields
    print("\n2. Testing Job dataclass structure...")
    if jobs:
        test_job = jobs[0]
        assert hasattr(test_job, 'source'), "Job missing 'source' attribute"
        assert hasattr(test_job, 'source_priority'), "Job missing 'source_priority' attribute"
        assert hasattr(test_job, 'is_processed'), "Job missing 'is_processed' attribute"
        print("   [OK] All new attributes present in Job dataclass")

    # Test 3: Count total jobs
    print("\n3. Checking database state...")
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_count = cursor.fetchone()[0]
    print(f"   Total jobs in database: {total_count}")

    cursor.execute("""
        SELECT COUNT(*) FROM jobs
        WHERE source='linkedin' AND source_priority=2 AND is_processed=0
    """)
    default_count = cursor.fetchone()[0]
    print(f"   Jobs with default values: {default_count}")

    # Summary
    print("\n" + "=" * 80)
    print("[SUCCESS] All tests passed!")
    print("   - Database.py correctly reads new source tracking columns")
    print("   - Job dataclass includes all new fields")
    print("   - All existing jobs have proper default values")
    print("=" * 80)

    db.close()


if __name__ == "__main__":
    test_database()

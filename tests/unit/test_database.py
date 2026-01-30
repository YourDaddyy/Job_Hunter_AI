"""Unit tests for the database module."""

import pytest
import sqlite3
from datetime import datetime
from src.core.database import Database, Job


@pytest.fixture
def db():
    """Create an in-memory database for testing."""
    database = Database(":memory:")
    database.init_schema()
    yield database
    database.close()


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        'platform': 'linkedin',
        'external_id': 'job123',
        'url': 'https://linkedin.com/jobs/123',
        'title': 'Senior Python Developer',
        'company': 'TechCorp',
        'location': 'San Francisco, CA',
        'salary_min': 120000,
        'salary_max': 180000,
        'salary_currency': 'USD',
        'remote_type': 'remote',
        'visa_sponsorship': True,
        'easy_apply': True,
        'jd_markdown': '# Job Description\nWe are looking for...',
        'jd_raw': '<html><body>We are looking for...</body></html>',
    }


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_init_schema_creates_tables(self, db):
        """Test that init_schema creates all required tables."""
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ['applications', 'blacklist', 'jobs', 'logs', 'resumes', 'runs']
        assert tables == expected_tables

    def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled for file-based databases."""
        # Note: WAL mode is not enabled for :memory: databases
        db = Database("data/test_wal.db")
        db.init_schema()

        cursor = db.conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]

        assert mode.lower() == 'wal'
        db.close()

        # Cleanup
        import os
        if os.path.exists("data/test_wal.db"):
            os.remove("data/test_wal.db")
        if os.path.exists("data/test_wal.db-wal"):
            os.remove("data/test_wal.db-wal")
        if os.path.exists("data/test_wal.db-shm"):
            os.remove("data/test_wal.db-shm")

    def test_foreign_keys_enabled(self, db):
        """Test that foreign keys are enabled."""
        cursor = db.conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        enabled = cursor.fetchone()[0]

        assert enabled == 1


class TestJobOperations:
    """Tests for job CRUD operations."""

    def test_insert_job(self, db, sample_job_data):
        """Test inserting a new job."""
        job_id = db.insert_job(sample_job_data)

        assert job_id is not None
        assert job_id > 0

        # Verify job was inserted
        job = db.get_job_by_id(job_id)
        assert job is not None
        assert job.title == 'Senior Python Developer'
        assert job.company == 'TechCorp'
        assert job.platform == 'linkedin'

    def test_insert_job_calculates_url_hash(self, db, sample_job_data):
        """Test that url_hash is calculated correctly."""
        job_id = db.insert_job(sample_job_data)
        job = db.get_job_by_id(job_id)

        import hashlib
        expected_hash = hashlib.md5(sample_job_data['url'].encode()).hexdigest()
        assert job.url_hash == expected_hash

    def test_insert_duplicate_job_raises_error(self, db, sample_job_data):
        """Test that inserting duplicate job raises IntegrityError."""
        db.insert_job(sample_job_data)

        with pytest.raises(sqlite3.IntegrityError):
            db.insert_job(sample_job_data)

    def test_insert_job_if_new_returns_id(self, db, sample_job_data):
        """Test insert_job_if_new with new job."""
        job_id = db.insert_job_if_new(sample_job_data)

        assert job_id is not None
        assert job_id > 0

    def test_insert_job_if_new_returns_none_for_duplicate(self, db, sample_job_data):
        """Test insert_job_if_new with duplicate job."""
        db.insert_job(sample_job_data)
        job_id = db.insert_job_if_new(sample_job_data)

        assert job_id is None

    def test_get_job_by_id_not_found(self, db):
        """Test getting non-existent job returns None."""
        job = db.get_job_by_id(999)
        assert job is None

    def test_get_jobs_by_status(self, db, sample_job_data):
        """Test getting jobs by status."""
        # Insert jobs with different statuses
        db.insert_job(sample_job_data)

        sample_job_data['url'] = 'https://linkedin.com/jobs/124'
        sample_job_data['external_id'] = 'job124'
        job_id2 = db.insert_job(sample_job_data)
        db.update_job_status(job_id2, 'filtered')

        sample_job_data['url'] = 'https://linkedin.com/jobs/125'
        sample_job_data['external_id'] = 'job125'
        job_id3 = db.insert_job(sample_job_data)
        db.update_job_status(job_id3, 'filtered')

        # Get filtered jobs
        filtered_jobs = db.get_jobs_by_status('filtered')
        assert len(filtered_jobs) == 2

        # Get new jobs
        new_jobs = db.get_jobs_by_status('new')
        assert len(new_jobs) == 1

    def test_get_jobs_by_status_with_limit(self, db, sample_job_data):
        """Test getting jobs by status with limit."""
        # Insert 5 jobs
        for i in range(5):
            sample_job_data['url'] = f'https://linkedin.com/jobs/{i}'
            sample_job_data['external_id'] = f'job{i}'
            db.insert_job(sample_job_data)

        jobs = db.get_jobs_by_status('new', limit=3)
        assert len(jobs) == 3

    def test_update_job_status(self, db, sample_job_data):
        """Test updating job status."""
        job_id = db.insert_job(sample_job_data)
        db.update_job_status(job_id, 'filtered', decision_type='auto')

        job = db.get_job_by_id(job_id)
        assert job.status == 'filtered'
        assert job.decision_type == 'auto'
        assert job.filtered_at is not None

    def test_update_job_filter_results(self, db, sample_job_data):
        """Test updating job with filter results."""
        job_id = db.insert_job(sample_job_data)

        requirements = ['Python', '5+ years experience', 'Django']
        red_flags = ['No remote work', 'Low salary']

        db.update_job_filter_results(
            job_id,
            score=0.85,
            reasoning='Great match for skills',
            requirements=requirements,
            red_flags=red_flags
        )

        job = db.get_job_by_id(job_id)
        assert job.match_score == 0.85
        assert job.match_reasoning == 'Great match for skills'
        assert job.key_requirements == requirements
        assert job.red_flags == red_flags
        assert job.status == 'filtered'

    def test_get_matched_jobs(self, db, sample_job_data):
        """Test getting matched jobs by score."""
        # Insert jobs with different scores
        job_id1 = db.insert_job(sample_job_data)
        db.update_job_filter_results(job_id1, 0.9, 'Great', [], [])
        db.update_job_status(job_id1, 'matched')

        sample_job_data['url'] = 'https://linkedin.com/jobs/124'
        sample_job_data['external_id'] = 'job124'
        job_id2 = db.insert_job(sample_job_data)
        db.update_job_filter_results(job_id2, 0.7, 'Good', [], [])
        db.update_job_status(job_id2, 'matched')

        sample_job_data['url'] = 'https://linkedin.com/jobs/125'
        sample_job_data['external_id'] = 'job125'
        job_id3 = db.insert_job(sample_job_data)
        db.update_job_filter_results(job_id3, 0.5, 'Okay', [], [])
        db.update_job_status(job_id3, 'matched')

        # Get jobs with score >= 0.6
        matched = db.get_matched_jobs(min_score=0.6)
        assert len(matched) == 2
        assert matched[0].match_score == 0.9  # Sorted by score DESC



    def test_get_daily_stats(self, db, sample_job_data):
        """Test getting daily statistics."""
        # Add scraped_at to sample data
        sample_job_data['scraped_at'] = datetime.now()
        
        # Insert jobs with different statuses
        db.insert_job(sample_job_data)
        
        sample_job_data['url'] = 'https://linkedin.com/jobs/124'
        sample_job_data['external_id'] = 'job124'
        job_id2 = db.insert_job(sample_job_data)
        db.update_job_filter_results(job_id2, 0.9, 'Great', [], [])
        db.update_job_status(job_id2, 'matched', decision_type='auto')
        
        sample_job_data['url'] = 'https://linkedin.com/jobs/125'
        sample_job_data['external_id'] = 'job125'
        job_id3 = db.insert_job(sample_job_data)
        db.update_job_filter_results(job_id3, 0.5, 'Poor', [], [])
        db.update_job_status(job_id3, 'rejected')
        
        # Get stats for today
        stats = db.get_daily_stats(datetime.now())
        
        assert stats is not None
        assert stats['scraped'] == 3
        assert stats['high_match'] == 1  # Score 0.9
        assert stats['rejected'] == 1    # Score 0.5
        assert stats['medium_match'] == 0 # No medium match inserted


class TestDeduplication:
    """Tests for duplicate detection."""

    def test_check_duplicate_by_external_id(self, db, sample_job_data):
        """Test duplicate detection by external_id."""
        db.insert_job(sample_job_data)

        result = db.check_duplicate(
            platform='linkedin',
            external_id='job123'
        )

        assert result['is_duplicate'] is True
        assert result['reason'] == 'already_scraped'
        assert result['existing_job_id'] is not None

    def test_check_duplicate_by_url(self, db, sample_job_data):
        """Test duplicate detection by URL."""
        db.insert_job(sample_job_data)

        result = db.check_duplicate(url='https://linkedin.com/jobs/123')

        assert result['is_duplicate'] is True
        assert result['reason'] == 'already_scraped'

    def test_check_duplicate_not_found(self, db):
        """Test duplicate check for non-existent job."""
        result = db.check_duplicate(
            platform='linkedin',
            external_id='nonexistent'
        )

        assert result['is_duplicate'] is False
        assert result['reason'] is None
        assert result['existing_job_id'] is None

    def test_check_duplicate_already_applied(self, db, sample_job_data):
        """Test duplicate detection for applied job."""
        job_id = db.insert_job(sample_job_data)
        db.update_job_status(job_id, 'applied')

        result = db.check_duplicate(
            platform='linkedin',
            external_id='job123'
        )

        assert result['is_duplicate'] is True
        assert result['reason'] == 'already_applied'


class TestApplicationOperations:
    """Tests for application tracking."""

    def test_insert_application(self, db, sample_job_data):
        """Test inserting application record."""
        job_id = db.insert_job(sample_job_data)

        app_id = db.insert_application(
            job_id,
            resume_path='/path/to/resume.pdf',
            cover_letter_path='/path/to/cover.pdf'
        )

        assert app_id is not None
        assert app_id > 0

    def test_update_application_status(self, db, sample_job_data):
        """Test updating application status."""
        job_id = db.insert_job(sample_job_data)
        db.insert_application(job_id, '/path/to/resume.pdf')

        db.update_application_status(job_id, 'submitted')

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        app = cursor.fetchone()

        assert app['status'] == 'submitted'
        assert app['submitted_at'] is not None
        assert app['attempts'] == 1

    def test_update_application_status_with_error(self, db, sample_job_data):
        """Test updating application status with error."""
        job_id = db.insert_job(sample_job_data)
        db.insert_application(job_id, '/path/to/resume.pdf')

        db.update_application_status(job_id, 'failed', error_message='Network error')

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,))
        app = cursor.fetchone()

        assert app['status'] == 'failed'
        assert app['error_message'] == 'Network error'

    def test_get_application_count_today(self, db, sample_job_data):
        """Test counting today's applications."""
        job_id1 = db.insert_job(sample_job_data)
        db.insert_application(job_id1, '/path/to/resume.pdf')
        db.update_application_status(job_id1, 'submitted')

        sample_job_data['url'] = 'https://linkedin.com/jobs/124'
        sample_job_data['external_id'] = 'job124'
        job_id2 = db.insert_job(sample_job_data)
        db.insert_application(job_id2, '/path/to/resume.pdf')
        db.update_application_status(job_id2, 'submitted')

        count = db.get_application_count_today()
        assert count == 2


class TestResumeOperations:
    """Tests for resume tracking."""

    def test_insert_resume(self, db, sample_job_data):
        """Test inserting resume record."""
        job_id = db.insert_job(sample_job_data)

        resume_id = db.insert_resume(
            job_id,
            pdf_path='/path/to/resume.pdf',
            highlights=['Achievement 1', 'Achievement 2'],
            tailoring_notes='Emphasized Python skills'
        )

        assert resume_id is not None
        assert resume_id > 0

    def test_get_resume_for_job(self, db, sample_job_data):
        """Test getting resume for a job."""
        job_id = db.insert_job(sample_job_data)
        highlights = ['Achievement 1', 'Achievement 2']

        db.insert_resume(
            job_id,
            '/path/to/resume.pdf',
            highlights=highlights,
            tailoring_notes='Custom notes'
        )

        resume = db.get_resume_for_job(job_id)

        assert resume is not None
        assert resume['job_id'] == job_id
        assert resume['pdf_path'] == '/path/to/resume.pdf'
        assert resume['highlights'] == highlights
        assert resume['tailoring_notes'] == 'Custom notes'

    def test_get_resume_for_job_not_found(self, db, sample_job_data):
        """Test getting resume for job without resume."""
        job_id = db.insert_job(sample_job_data)
        resume = db.get_resume_for_job(job_id)

        assert resume is None


class TestRunTracking:
    """Tests for run tracking."""

    def test_start_run(self, db):
        """Test starting a new run."""
        run_id = db.start_run()

        assert run_id is not None
        assert run_id > 0

    def test_update_run_stats(self, db):
        """Test updating run statistics."""
        run_id = db.start_run()

        db.update_run_stats(
            run_id,
            jobs_scraped=10,
            jobs_filtered=8,
            jobs_matched=5
        )

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()

        assert run['jobs_scraped'] == 10
        assert run['jobs_filtered'] == 8
        assert run['jobs_matched'] == 5

    def test_complete_run(self, db):
        """Test completing a run."""
        run_id = db.start_run()
        db.complete_run(run_id, status='completed')

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        run = cursor.fetchone()

        assert run['status'] == 'completed'
        assert run['completed_at'] is not None

    def test_get_current_run(self, db):
        """Test getting current running run."""
        run_id = db.start_run()
        current = db.get_current_run()

        assert current is not None
        assert current['id'] == run_id
        assert current['status'] == 'running'

    def test_get_current_run_none_when_completed(self, db):
        """Test get_current_run returns None when no running runs."""
        run_id = db.start_run()
        db.complete_run(run_id)

        current = db.get_current_run()
        assert current is None


class TestBlacklist:
    """Tests for blacklist operations."""

    def test_add_to_blacklist(self, db):
        """Test adding to blacklist."""
        db.add_to_blacklist('company', 'BadCorp', 'Poor reviews')

        blacklist = db.get_blacklist()
        assert len(blacklist) == 1
        assert blacklist[0]['type'] == 'company'
        assert blacklist[0]['value'] == 'BadCorp'
        assert blacklist[0]['reason'] == 'Poor reviews'

    def test_add_duplicate_to_blacklist_ignored(self, db):
        """Test that duplicate blacklist entries are ignored."""
        db.add_to_blacklist('company', 'BadCorp', 'Poor reviews')
        db.add_to_blacklist('company', 'BadCorp', 'Poor reviews')

        blacklist = db.get_blacklist()
        assert len(blacklist) == 1

    def test_is_blacklisted(self, db):
        """Test checking if company is blacklisted."""
        db.add_to_blacklist('company', 'BadCorp')

        assert db.is_blacklisted('BadCorp') is True
        assert db.is_blacklisted('GoodCorp') is False

    def test_get_blacklist(self, db):
        """Test getting all blacklist entries."""
        db.add_to_blacklist('company', 'Company1')
        db.add_to_blacklist('keyword', 'unpaid')
        db.add_to_blacklist('company', 'Company2')

        blacklist = db.get_blacklist()
        assert len(blacklist) == 3


class TestLogging:
    """Tests for logging operations."""

    def test_log_simple(self, db):
        """Test simple log entry."""
        db.log('info', 'scraper', 'Job scraped successfully')

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 1")
        log = cursor.fetchone()

        assert log['level'] == 'info'
        assert log['component'] == 'scraper'
        assert log['message'] == 'Job scraped successfully'
        assert log['details'] is None

    def test_log_with_details(self, db):
        """Test log entry with details."""
        details = {'job_id': 123, 'platform': 'linkedin'}
        db.log('error', 'applier', 'Application failed', details=details)

        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 1")
        log = cursor.fetchone()

        assert log['level'] == 'error'
        assert log['details'] is not None

        import json
        assert json.loads(log['details']) == details


class TestTransactions:
    """Tests for transaction support."""

    def test_transaction_commit(self, db, sample_job_data):
        """Test successful transaction commit."""
        with db.transaction():
            job_id = db.insert_job(sample_job_data)

        # Verify job was committed
        job = db.get_job_by_id(job_id)
        assert job is not None

    def test_transaction_rollback(self, db, sample_job_data):
        """Test transaction rollback on error."""
        try:
            with db.transaction():
                job_id = db.insert_job(sample_job_data)
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify job was rolled back
        cursor = db.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM jobs")
        count = cursor.fetchone()['count']
        assert count == 0


class TestJobDataclassParsing:
    """Tests for Job dataclass JSON field parsing."""

    def test_job_dataclass_parses_json_fields(self, db, sample_job_data):
        """Test that Job dataclass correctly parses JSON fields."""
        job_id = db.insert_job(sample_job_data)

        requirements = ['Python', 'Django']
        red_flags = ['Low salary']

        db.update_job_filter_results(
            job_id,
            score=0.8,
            reasoning='Good match',
            requirements=requirements,
            red_flags=red_flags
        )

        job = db.get_job_by_id(job_id)

        assert isinstance(job.key_requirements, list)
        assert job.key_requirements == requirements
        assert isinstance(job.red_flags, list)
        assert job.red_flags == red_flags

    def test_job_dataclass_handles_null_json_fields(self, db, sample_job_data):
        """Test that Job dataclass handles NULL JSON fields."""
        job_id = db.insert_job(sample_job_data)
        job = db.get_job_by_id(job_id)

        assert job.key_requirements is None
        assert job.red_flags is None

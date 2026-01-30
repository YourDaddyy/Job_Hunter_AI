"""SQLite database module for job tracking and management."""

import sqlite3
import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path


@dataclass
class Job:
    """Job record from database."""
    id: int
    external_id: Optional[str]
    platform: str
    url: str
    url_hash: str
    fuzzy_hash: Optional[str]  # Hash for fuzzy deduplication (company+title)
    title: str
    company: str
    location: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    salary_currency: str
    remote_type: Optional[str]
    visa_sponsorship: Optional[bool]
    easy_apply: bool
    jd_markdown: Optional[str]
    jd_raw: Optional[str]
    match_score: Optional[float]
    match_reasoning: Optional[str]
    key_requirements: Optional[List[str]]  # Parsed from JSON
    red_flags: Optional[List[str]]         # Parsed from JSON
    status: str
    decision_type: Optional[str]
    source: str  # Source platform (e.g., 'linkedin', 'indeed')
    source_priority: int  # Priority for processing (1=high, 2=medium, 3=low)
    is_processed: bool  # Whether job has been processed/filtered
    scraped_at: datetime
    filtered_at: Optional[datetime]
    decided_at: Optional[datetime]
    applied_at: Optional[datetime]


@dataclass
class Application:
    """Application record from database."""
    id: int
    job_id: int
    resume_path: Optional[str]
    cover_letter_path: Optional[str]
    status: str
    error_message: Optional[str]
    attempts: int
    submitted_at: Optional[datetime]
    created_at: datetime


@dataclass
class Resume:
    """Resume record from database."""
    id: int
    job_id: int
    pdf_path: str
    html_content: Optional[str]
    highlights: Optional[List[str]]
    tailoring_notes: Optional[str]
    generated_at: datetime


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str = "data/jobs.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
                     Use ":memory:" for testing.
        """
        self.db_path = db_path

        # Create parent directory if it doesn't exist
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent read performance
        if db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")

        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys=ON")

    # === Initialization ===

    def init_schema(self) -> None:
        """Create all tables if they don't exist."""
        cursor = self.conn.cursor()

        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Identification (for deduplication)
                external_id TEXT,
                url_hash TEXT,
                fuzzy_hash TEXT,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,

                -- Job details
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_currency TEXT DEFAULT 'USD',
                remote_type TEXT,
                visa_sponsorship BOOLEAN,
                easy_apply BOOLEAN DEFAULT FALSE,

                -- Content
                jd_markdown TEXT,
                jd_raw TEXT,

                -- Filtering results
                match_score REAL,
                match_reasoning TEXT,
                key_requirements TEXT,
                red_flags TEXT,

                -- Status tracking
                status TEXT DEFAULT 'new',
                decision_type TEXT,

                -- Source tracking
                source TEXT DEFAULT 'linkedin',
                source_priority INTEGER DEFAULT 2,
                is_processed BOOLEAN DEFAULT 0,

                -- Timestamps
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                filtered_at TIMESTAMP,
                decided_at TIMESTAMP,
                applied_at TIMESTAMP,

                -- Constraints
                UNIQUE(platform, external_id),
                UNIQUE(url_hash)
            )
        """)

        # Create indexes for jobs table
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_match_score ON jobs(match_score)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs(scraped_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_platform ON jobs(platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_fuzzy_hash ON jobs(fuzzy_hash)")

        # Applications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER UNIQUE REFERENCES jobs(id),
                resume_path TEXT,
                cover_letter_path TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                submitted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")

        # Resumes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                pdf_path TEXT NOT NULL,
                html_content TEXT,
                highlights TEXT,
                tailoring_notes TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumes_job_id ON resumes(job_id)")

        # Runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                jobs_scraped INTEGER DEFAULT 0,
                jobs_filtered INTEGER DEFAULT 0,
                jobs_matched INTEGER DEFAULT 0,
                jobs_auto_applied INTEGER DEFAULT 0,
                jobs_pending_decision INTEGER DEFAULT 0,
                jobs_failed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running'
            )
        """)

        # Blacklist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(type, value)
            )
        """)

        # Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                component TEXT,
                message TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_component ON logs(component)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at)")

        self.conn.commit()

    # === Job Operations ===

    def insert_job(self, job_data: Dict[str, Any]) -> int:
        """Insert a new job record.

        Args:
            job_data: Dictionary with job fields from scraper

        Returns:
            New job ID

        Raises:
            IntegrityError: If duplicate external_id or url_hash
        """
        # Calculate url_hash
        url_hash = hashlib.md5(job_data['url'].encode()).hexdigest()

        # Serialize list fields to JSON
        key_requirements_json = json.dumps(job_data.get('key_requirements')) if job_data.get('key_requirements') else None
        red_flags_json = json.dumps(job_data.get('red_flags')) if job_data.get('red_flags') else None

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO jobs (
                external_id, url_hash, fuzzy_hash, platform, url,
                title, company, location,
                salary_min, salary_max, salary_currency,
                remote_type, visa_sponsorship, easy_apply,
                jd_markdown, jd_raw,
                match_score, match_reasoning, key_requirements, red_flags,
                status, decision_type,
                source, source_priority, is_processed,
                scraped_at, filtered_at, decided_at, applied_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_data.get('external_id'),
            url_hash,
            job_data.get('fuzzy_hash'),
            job_data['platform'],
            job_data['url'],
            job_data['title'],
            job_data['company'],
            job_data.get('location'),
            job_data.get('salary_min'),
            job_data.get('salary_max'),
            job_data.get('salary_currency', 'USD'),
            job_data.get('remote_type'),
            job_data.get('visa_sponsorship'),
            job_data.get('easy_apply', False),
            job_data.get('jd_markdown'),
            job_data.get('jd_raw'),
            job_data.get('match_score'),
            job_data.get('match_reasoning'),
            key_requirements_json,
            red_flags_json,
            job_data.get('status', 'new'),
            job_data.get('decision_type'),
            job_data.get('source', 'linkedin'),
            job_data.get('source_priority', 2),
            job_data.get('is_processed', False),
            job_data.get('scraped_at'),
            job_data.get('filtered_at'),
            job_data.get('decided_at'),
            job_data.get('applied_at')
        ))

        self.conn.commit()
        return cursor.lastrowid

    def insert_job_if_new(self, job_data: Dict[str, Any]) -> Optional[int]:
        """Insert job only if not duplicate.

        Returns:
            Job ID if inserted, None if duplicate
        """
        # Check for duplicates first
        duplicate_check = self.check_duplicate(
            platform=job_data['platform'],
            external_id=job_data.get('external_id'),
            url=job_data['url']
        )

        if duplicate_check['is_duplicate']:
            return None

        try:
            return self.insert_job(job_data)
        except sqlite3.IntegrityError:
            # Race condition - another process inserted it
            return None

    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """Get single job by ID."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_job(row)

    def get_jobs_by_status(
        self,
        status: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Job]:
        """Get jobs with specific status."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY scraped_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset)
        )

        return [self._row_to_job(row) for row in cursor.fetchall()]

    def get_matched_jobs(
        self,
        min_score: float = 0.60,
        max_score: float = 1.0,
        status: str = "matched",
        limit: int = 20
    ) -> List[Job]:
        """Get jobs within score range."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM jobs
            WHERE status = ?
            AND match_score >= ?
            AND match_score <= ?
            ORDER BY match_score DESC
            LIMIT ?
        """, (status, min_score, max_score, limit))

        return [self._row_to_job(row) for row in cursor.fetchall()]

    def update_job_status(
        self,
        job_id: int,
        status: str,
        decision_type: Optional[str] = None
    ) -> None:
        """Update job status."""
        cursor = self.conn.cursor()

        # Set appropriate timestamp based on status
        timestamp_field = None
        if status == 'filtered':
            timestamp_field = 'filtered_at'
        elif status in ['approved', 'rejected', 'skipped']:
            timestamp_field = 'decided_at'
        elif status == 'applied':
            timestamp_field = 'applied_at'

        if timestamp_field:
            cursor.execute(f"""
                UPDATE jobs
                SET status = ?, decision_type = ?, {timestamp_field} = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, decision_type, job_id))
        else:
            cursor.execute("""
                UPDATE jobs
                SET status = ?, decision_type = ?
                WHERE id = ?
            """, (status, decision_type, job_id))

        self.conn.commit()

    def update_job_filter_results(
        self,
        job_id: int,
        score: float,
        reasoning: str,
        requirements: List[str],
        red_flags: List[str]
    ) -> None:
        """Update job with filtering results."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET match_score = ?,
                match_reasoning = ?,
                key_requirements = ?,
                red_flags = ?,
                filtered_at = CURRENT_TIMESTAMP,
                status = 'filtered'
            WHERE id = ?
        """, (
            score,
            reasoning,
            json.dumps(requirements),
            json.dumps(red_flags),
            job_id
        ))

        self.conn.commit()

    # === Deduplication ===

    def check_duplicate(
        self,
        platform: Optional[str] = None,
        external_id: Optional[str] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Check if job already exists.

        Returns:
            {
                "is_duplicate": bool,
                "reason": "already_applied" | "already_scraped" | "blacklisted" | None,
                "existing_job_id": int | None
            }
        """
        cursor = self.conn.cursor()

        # Check by external_id and platform
        if platform and external_id:
            cursor.execute(
                "SELECT id, status FROM jobs WHERE platform = ? AND external_id = ?",
                (platform, external_id)
            )
            row = cursor.fetchone()
            if row:
                reason = "already_applied" if row['status'] == 'applied' else "already_scraped"
                return {
                    "is_duplicate": True,
                    "reason": reason,
                    "existing_job_id": row['id']
                }

        # Check by url_hash
        if url:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            cursor.execute("SELECT id, status FROM jobs WHERE url_hash = ?", (url_hash,))
            row = cursor.fetchone()
            if row:
                reason = "already_applied" if row['status'] == 'applied' else "already_scraped"
                return {
                    "is_duplicate": True,
                    "reason": reason,
                    "existing_job_id": row['id']
                }

        return {
            "is_duplicate": False,
            "reason": None,
            "existing_job_id": None
        }

    # === Application Operations ===

    def insert_application(
        self,
        job_id: int,
        resume_path: str,
        cover_letter_path: Optional[str] = None
    ) -> int:
        """Create application record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO applications (job_id, resume_path, cover_letter_path)
            VALUES (?, ?, ?)
        """, (job_id, resume_path, cover_letter_path))

        self.conn.commit()
        return cursor.lastrowid

    def update_application_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update application status."""
        cursor = self.conn.cursor()

        if status == 'submitted':
            cursor.execute("""
                UPDATE applications
                SET status = ?, error_message = ?, submitted_at = CURRENT_TIMESTAMP,
                    attempts = attempts + 1
                WHERE job_id = ?
            """, (status, error_message, job_id))
        else:
            cursor.execute("""
                UPDATE applications
                SET status = ?, error_message = ?, attempts = attempts + 1
                WHERE job_id = ?
            """, (status, error_message, job_id))

        self.conn.commit()

    def get_application_count_today(self) -> int:
        """Get number of applications submitted today."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM applications
            WHERE status = 'submitted'
            AND DATE(submitted_at) = DATE('now')
        """)

        row = cursor.fetchone()
        return row['count'] if row else 0

    # === Resume Operations ===

    def insert_resume(
        self,
        job_id: int,
        pdf_path: str,
        highlights: List[str],
        tailoring_notes: str
    ) -> int:
        """Save generated resume record."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO resumes (job_id, pdf_path, highlights, tailoring_notes)
            VALUES (?, ?, ?, ?)
        """, (job_id, pdf_path, json.dumps(highlights), tailoring_notes))

        self.conn.commit()
        return cursor.lastrowid

    def get_resume_for_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get resume info for a job."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM resumes WHERE job_id = ? ORDER BY generated_at DESC LIMIT 1",
            (job_id,)
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            'id': row['id'],
            'job_id': row['job_id'],
            'pdf_path': row['pdf_path'],
            'html_content': row['html_content'],
            'highlights': json.loads(row['highlights']) if row['highlights'] else None,
            'tailoring_notes': row['tailoring_notes'],
            'generated_at': row['generated_at']
        }

    # === Run Tracking ===

    def start_run(self) -> int:
        """Create new run record, return run_id."""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO runs DEFAULT VALUES")

        self.conn.commit()
        return cursor.lastrowid

    def update_run_stats(self, run_id: int, **stats) -> None:
        """Update run statistics."""
        # Build dynamic UPDATE query based on provided stats
        valid_fields = [
            'jobs_scraped', 'jobs_filtered', 'jobs_matched',
            'jobs_auto_applied', 'jobs_pending_decision', 'jobs_failed'
        ]

        updates = []
        values = []
        for key, value in stats.items():
            if key in valid_fields:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return

        values.append(run_id)

        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE runs SET {', '.join(updates)} WHERE id = ?",
            values
        )

        self.conn.commit()

    def complete_run(self, run_id: int, status: str = "completed") -> None:
        """Mark run as complete."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE runs
            SET completed_at = CURRENT_TIMESTAMP, status = ?
            WHERE id = ?
        """, (status, run_id))

        self.conn.commit()

    def get_current_run(self) -> Optional[Dict[str, Any]]:
        """Get the latest running run."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        if not row:
            return None

        return dict(row)

    def get_daily_stats(self, date) -> dict:
        """Get comprehensive statistics for a specific date.
        
        Args:
            date: Date object to get statistics for
            
        Returns:
            Dictionary with keys:
            - scraped: Total jobs scraped
            - high_match: Jobs with match_score >= 0.85
            - medium_match: Jobs with match_score >= 0.60 and < 0.85
            - rejected: Jobs with match_score < 0.60
            - auto_applied: Jobs auto-applied
            - manual_applied: Jobs manually approved and applied
            - failed: Failed applications
            - pending: Jobs pending decision
            - success_rate: Application success rate (0.0-1.0)
            - glm_cost: Estimated GLM API cost
            - claude_cost: Estimated Claude API cost
            - total_cost: Total estimated cost
        """
        cursor = self.conn.cursor()
        date_str = date.strftime('%Y-%m-%d')
        
        # Get job counts by match score
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN match_score >= 0.85 THEN 1 ELSE 0 END) as high_match,
                SUM(CASE WHEN match_score >= 0.60 AND match_score < 0.85 THEN 1 ELSE 0 END) as medium_match,
                SUM(CASE WHEN match_score < 0.60 THEN 1 ELSE 0 END) as rejected
            FROM jobs
            WHERE DATE(scraped_at) = ?
        """, (date_str,))
        
        job_stats = cursor.fetchone()
        
        # Get application counts
        cursor.execute("""
            SELECT 
                COUNT(*) as total_applied,
                SUM(CASE WHEN j.decision_type = 'auto' THEN 1 ELSE 0 END) as auto_applied,
                SUM(CASE WHEN j.decision_type = 'manual' THEN 1 ELSE 0 END) as manual_applied
            FROM jobs j
            WHERE DATE(j.applied_at) = ?
            AND j.status = 'applied'
        """, (date_str,))
        
        app_stats = cursor.fetchone()
        
        # Get failed applications
        cursor.execute("""
            SELECT COUNT(*) as failed
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE DATE(j.applied_at) = ?
            AND a.status = 'failed'
        """, (date_str,))
        
        failed_row = cursor.fetchone()
        
        # Get pending decisions
        cursor.execute("""
            SELECT COUNT(*) as pending
            FROM jobs
            WHERE status = 'pending_decision'
        """)
        
        pending_row = cursor.fetchone()
        
        # Calculate success rate
        total_applied = app_stats['total_applied'] or 0
        failed = failed_row['failed'] or 0
        success_rate = (total_applied - failed) / total_applied if total_applied > 0 else 0.0
        
        # Calculate costs (estimates)
        # GLM: $0.001 per job filtered
        # Claude: $0.01 per resume tailored/applied
        scraped = job_stats['total'] or 0
        glm_cost = scraped * 0.001
        claude_cost = total_applied * 0.01
        
        return {
            'scraped': scraped,
            'high_match': job_stats['high_match'] or 0,
            'medium_match': job_stats['medium_match'] or 0,
            'rejected': job_stats['rejected'] or 0,
            'auto_applied': app_stats['auto_applied'] or 0,
            'manual_applied': app_stats['manual_applied'] or 0,
            'failed': failed,
            'pending': pending_row['pending'] or 0,
            'success_rate': success_rate,
            'glm_cost': glm_cost,
            'claude_cost': claude_cost,
            'total_cost': glm_cost + claude_cost
        }


    # === Blacklist ===

    def add_to_blacklist(
        self,
        type: str,
        value: str,
        reason: Optional[str] = None
    ) -> None:
        """Add item to blacklist."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO blacklist (type, value, reason)
                VALUES (?, ?, ?)
            """, (type, value, reason))
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Already exists, ignore
            pass

    def is_blacklisted(self, company: str) -> bool:
        """Check if company is blacklisted."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM blacklist WHERE type = 'company' AND value = ?",
            (company,)
        )

        row = cursor.fetchone()
        return row['count'] > 0 if row else False

    def get_blacklist(self) -> List[Dict[str, Any]]:
        """Get all blacklist entries."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM blacklist ORDER BY created_at DESC")

        return [dict(row) for row in cursor.fetchall()]

    # === Logging ===

    def log(
        self,
        level: str,
        component: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Insert log entry."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO logs (level, component, message, details)
            VALUES (?, ?, ?, ?)
        """, (level, component, message, json.dumps(details) if details else None))

        self.conn.commit()

    # === Utility ===

    @contextmanager
    def transaction(self):
        """Context manager for transactions."""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    # === Private Helpers ===

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job dataclass."""
        # Helper to safely get values with defaults
        def safe_get(key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return Job(
            id=row['id'],
            external_id=row['external_id'],
            platform=row['platform'],
            url=row['url'],
            url_hash=row['url_hash'],
            fuzzy_hash=safe_get('fuzzy_hash'),
            title=row['title'],
            company=row['company'],
            location=row['location'],
            salary_min=row['salary_min'],
            salary_max=row['salary_max'],
            salary_currency=row['salary_currency'],
            remote_type=row['remote_type'],
            visa_sponsorship=row['visa_sponsorship'],
            easy_apply=bool(row['easy_apply']),
            jd_markdown=row['jd_markdown'],
            jd_raw=row['jd_raw'],
            match_score=row['match_score'],
            match_reasoning=row['match_reasoning'],
            key_requirements=json.loads(row['key_requirements']) if row['key_requirements'] else None,
            red_flags=json.loads(row['red_flags']) if row['red_flags'] else None,
            status=row['status'],
            decision_type=row['decision_type'],
            source=safe_get('source', 'linkedin'),
            source_priority=safe_get('source_priority', 2),
            is_processed=bool(safe_get('is_processed', False)),
            scraped_at=datetime.fromisoformat(row['scraped_at']) if row['scraped_at'] else None,
            filtered_at=datetime.fromisoformat(row['filtered_at']) if row['filtered_at'] else None,
            decided_at=datetime.fromisoformat(row['decided_at']) if row['decided_at'] else None,
            applied_at=datetime.fromisoformat(row['applied_at']) if row['applied_at'] else None
        )


# === CLI Commands ===

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.core.database <command>")
        print("Commands:")
        print("  init   - Initialize database schema")
        print("  stats  - Show database statistics")
        sys.exit(1)

    command = sys.argv[1]
    db = Database()

    if command == "init":
        print("Initializing database schema...")
        db.init_schema()
        print(f"Database initialized at: {db.db_path}")
        print("Tables created: jobs, applications, resumes, runs, blacklist, logs")

    elif command == "stats":
        print("Database Statistics")
        print("=" * 50)

        cursor = db.conn.cursor()

        # Job counts by status
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
            ORDER BY count DESC
        """)
        print("\nJobs by Status:")
        for row in cursor.fetchall():
            print(f"  {row['status']:<20} {row['count']:>5}")

        # Total jobs
        cursor.execute("SELECT COUNT(*) as count FROM jobs")
        total = cursor.fetchone()['count']
        print(f"\n  {'TOTAL':<20} {total:>5}")

        # Application stats
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM applications
            GROUP BY status
        """)
        print("\nApplications by Status:")
        for row in cursor.fetchall():
            print(f"  {row['status']:<20} {row['count']:>5}")

        # Platform distribution
        cursor.execute("""
            SELECT platform, COUNT(*) as count
            FROM jobs
            GROUP BY platform
            ORDER BY count DESC
        """)
        print("\nJobs by Platform:")
        for row in cursor.fetchall():
            print(f"  {row['platform']:<20} {row['count']:>5}")

        # Recent runs
        cursor.execute("""
            SELECT * FROM runs
            ORDER BY started_at DESC
            LIMIT 5
        """)
        print("\nRecent Runs:")
        runs = cursor.fetchall()
        if runs:
            for run in runs:
                print(f"  Run #{run['id']} - {run['status']}")
                print(f"    Started: {run['started_at']}")
                print(f"    Scraped: {run['jobs_scraped']}, Filtered: {run['jobs_filtered']}, Applied: {run['jobs_auto_applied']}")
        else:
            print("  No runs yet")

        # Blacklist count
        cursor.execute("SELECT COUNT(*) as count FROM blacklist")
        blacklist_count = cursor.fetchone()['count']
        print(f"\nBlacklist Entries: {blacklist_count}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

    db.close()

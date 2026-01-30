"""JSON Importer for Antigravity scraped data.

This module imports job data from JSON files scraped by Antigravity,
with intelligent deduplication at two levels:
1. URL exact match - Skip if URL already exists
2. Fuzzy hash match - Compare by company+title, apply source priority logic
"""

import json
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


def generate_fuzzy_hash(company: str, title: str) -> str:
    """Generate fuzzy hash for deduplication.

    Args:
        company: Company name
        title: Job title

    Returns:
        MD5 hash of normalized company+title
    """
    # Normalize: lowercase, strip whitespace
    key = f"{company.lower().strip()}{title.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()


def parse_salary(salary_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    """Parse salary string into min/max integers.

    Examples:
        "$150k-200k" -> (150000, 200000)
        "$150k-$200k" -> (150000, 200000)
        "$150,000-$200,000" -> (150000, 200000)
        "$150k+" -> (150000, None)
        "Up to $200k" -> (None, 200000)
        "Competitive" -> (None, None)

    Args:
        salary_str: Salary string from job posting

    Returns:
        Tuple of (min_salary, max_salary) in dollars
    """
    if not salary_str:
        return None, None

    # Remove currency symbols and normalize
    text = salary_str.lower().strip()
    text = text.replace('$', '').replace(',', '')

    # Try to find range pattern (e.g., "150k-200k", "150000-200000")
    range_match = re.search(r'(\d+\.?\d*)k?\s*-\s*(\d+\.?\d*)k?', text)
    if range_match:
        min_val = float(range_match.group(1))
        max_val = float(range_match.group(2))

        # Handle 'k' suffix
        if 'k' in text:
            min_val *= 1000
            max_val *= 1000

        return int(min_val), int(max_val)

    # Try to find "up to X" pattern
    up_to_match = re.search(r'up\s+to\s+(\d+\.?\d*)k?', text)
    if up_to_match:
        max_val = float(up_to_match.group(1))
        if 'k' in text:
            max_val *= 1000
        return None, int(max_val)

    # Try to find "X+" pattern
    plus_match = re.search(r'(\d+\.?\d*)k?\s*\+', text)
    if plus_match:
        min_val = float(plus_match.group(1))
        if 'k' in text:
            min_val *= 1000
        return int(min_val), None

    # Try to find single number
    single_match = re.search(r'(\d+\.?\d*)k?', text)
    if single_match:
        val = float(single_match.group(1))
        if 'k' in text:
            val *= 1000
        # If single value, treat as both min and max
        return int(val), int(val)

    return None, None


def determine_source_priority(source: str) -> int:
    """Determine source priority based on platform.

    Priority levels:
    1 = High priority (ATS platforms and text-heavy platforms)
    2 = Medium priority (visual platforms like LinkedIn, Glassdoor)
    3 = Low priority (aggregators)

    Args:
        source: Source platform name

    Returns:
        Priority level (1-3)
    """
    source_lower = source.lower()

    # High priority - ATS platforms (direct from companies) and text-heavy platforms
    if source_lower in ['greenhouse', 'lever', 'ashby', 'workable', 'indeed', 'wellfound']:
        return 1

    # Medium priority - visual platforms, may have less complete data
    elif source_lower in ['linkedin', 'glassdoor']:
        return 2

    # Low priority - aggregators
    else:
        return 3


def resolve_duplicate(
    existing_job: Dict[str, Any],
    new_job: Dict[str, Any]
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Compare two duplicate jobs and decide which to keep.

    Logic:
    1. If new_job.source_priority < existing.source_priority: UPDATE
    2. If equal priority:
       - If new description longer: UPDATE description only
       - Otherwise: SKIP
    3. If new_job.source_priority > existing: SKIP

    Args:
        existing_job: Job already in database
        new_job: New job being imported

    Returns:
        Tuple of (action, update_data):
        - ("skip", None) - Skip the new job
        - ("update_full", data) - Replace with new job
        - ("update_description", data) - Update only description
    """
    existing_priority = existing_job.get('source_priority', 2)
    new_priority = new_job.get('source_priority', 2)

    # Case 1: New source has higher priority (lower number)
    if new_priority < existing_priority:
        logger.info(
            f"Updating job {existing_job['id']}: New source has higher priority "
            f"({new_priority} < {existing_priority})"
        )
        return "update_full", new_job

    # Case 2: Same priority - compare data completeness
    elif new_priority == existing_priority:
        existing_desc = existing_job.get('jd_raw', '') or ''
        new_desc = new_job.get('description', '') or ''

        if len(new_desc) > len(existing_desc):
            logger.info(
                f"Updating description for job {existing_job['id']}: "
                f"New description is longer ({len(new_desc)} > {len(existing_desc)})"
            )
            return "update_description", {'jd_raw': new_desc, 'jd_markdown': new_desc}
        else:
            logger.debug(
                f"Skipping job: Same priority and new description not longer "
                f"({len(new_desc)} <= {len(existing_desc)})"
            )
            return "skip", None

    # Case 3: Existing source has higher priority
    else:
        logger.debug(
            f"Skipping job: Existing source has higher priority "
            f"({existing_priority} < {new_priority})"
        )
        return "skip", None


class AntigravityImporter:
    """Importer for Antigravity scraped JSON data."""

    def __init__(self, db: Optional[Database] = None):
        """Initialize importer.

        Args:
            db: Database instance (creates new if not provided)
        """
        self.db = db or Database()
        self.stats = {
            'total_jobs': 0,
            'new_jobs': 0,
            'url_duplicates': 0,
            'fuzzy_duplicates_skipped': 0,
            'fuzzy_duplicates_updated': 0,
            'by_source': {}
        }

    def import_json_file(self, file_path: str) -> Dict[str, Any]:
        """Import jobs from a single JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Statistics dictionary
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")

        logger.info(f"Importing jobs from: {file_path}")

        # Load JSON data
        with open(path, 'r', encoding='utf-8') as f:
            jobs_data = json.load(f)

        # Detect source from filename (e.g., "linkedin_scraped.json" -> "linkedin")
        source = self._detect_source_from_filename(path.name)
        logger.info(f"Detected source: {source}")

        # Initialize source stats
        if source not in self.stats['by_source']:
            self.stats['by_source'][source] = {
                'total': 0,
                'new': 0,
                'url_dup': 0,
                'fuzzy_dup_skip': 0,
                'fuzzy_dup_update': 0
            }

        # Process each job
        for job_raw in jobs_data:
            self._process_job(job_raw, source)

        logger.info(
            f"Import complete: {self.stats['new_jobs']} new, "
            f"{self.stats['url_duplicates']} URL duplicates, "
            f"{self.stats['fuzzy_duplicates_skipped']} fuzzy skipped, "
            f"{self.stats['fuzzy_duplicates_updated']} fuzzy updated"
        )

        return self.stats

    def import_multiple_files(self, file_paths: List[str] = None) -> Dict[str, Any]:
        """Import jobs from multiple JSON files.

        Args:
            file_paths: List of file paths. If None, auto-detect data/*.json

        Returns:
            Combined statistics dictionary
        """
        if file_paths is None:
            # Auto-detect JSON files in data directory
            data_dir = Path("W:\\Code\\job_viewer\\data")
            file_paths = list(data_dir.glob("*_scraped.json"))
            logger.info(f"Auto-detected {len(file_paths)} JSON files")

        if not file_paths:
            logger.warning("No JSON files found to import")
            return self.stats

        # Import each file
        for file_path in file_paths:
            try:
                self.import_json_file(str(file_path))
            except Exception as e:
                logger.error(f"Failed to import {file_path}: {e}", exc_info=True)

        return self.stats

    def _detect_source_from_filename(self, filename: str) -> str:
        """Detect source platform from filename.

        Args:
            filename: JSON filename

        Returns:
            Source name (linkedin, indeed, glassdoor, wellfound)
        """
        filename_lower = filename.lower()

        if 'linkedin' in filename_lower:
            return 'linkedin'
        elif 'indeed' in filename_lower:
            return 'indeed'
        elif 'glassdoor' in filename_lower:
            return 'glassdoor'
        elif 'wellfound' in filename_lower:
            return 'wellfound'
        else:
            # Default to filename without extension
            return filename.replace('_scraped.json', '').replace('.json', '')

    def _process_job(self, job_raw: Dict[str, Any], source: str) -> None:
        """Process a single job and insert/update in database.

        Args:
            job_raw: Raw job data from JSON
            source: Source platform name
        """
        self.stats['total_jobs'] += 1
        self.stats['by_source'][source]['total'] += 1

        # Normalize job data
        job_data = self._normalize_job_data(job_raw, source)

        # Check for URL exact match first
        url_hash = hashlib.md5(job_data['url'].encode()).hexdigest()
        existing_by_url = self._get_job_by_url_hash(url_hash)

        if existing_by_url:
            logger.debug(f"URL duplicate found: {job_data['url']}")
            self.stats['url_duplicates'] += 1
            self.stats['by_source'][source]['url_dup'] += 1
            return

        # Check for fuzzy hash match
        fuzzy_hash = job_data['fuzzy_hash']
        existing_by_fuzzy = self._get_job_by_fuzzy_hash(fuzzy_hash)

        if existing_by_fuzzy:
            logger.debug(
                f"Fuzzy duplicate found: {job_data['company']} - {job_data['title']}"
            )

            # Resolve duplicate
            action, update_data = resolve_duplicate(existing_by_fuzzy, job_data)

            if action == "skip":
                self.stats['fuzzy_duplicates_skipped'] += 1
                self.stats['by_source'][source]['fuzzy_dup_skip'] += 1

            elif action == "update_full":
                self._update_job(existing_by_fuzzy['id'], job_data)
                self.stats['fuzzy_duplicates_updated'] += 1
                self.stats['by_source'][source]['fuzzy_dup_update'] += 1

            elif action == "update_description":
                self._update_job_description(existing_by_fuzzy['id'], update_data)
                self.stats['fuzzy_duplicates_updated'] += 1
                self.stats['by_source'][source]['fuzzy_dup_update'] += 1

            return

        # No duplicates - insert new job
        try:
            job_id = self.db.insert_job(job_data)
            logger.debug(f"Inserted new job {job_id}: {job_data['company']} - {job_data['title']}")
            self.stats['new_jobs'] += 1
            self.stats['by_source'][source]['new'] += 1
        except Exception as e:
            logger.error(f"Failed to insert job: {e}", exc_info=True)

    def _normalize_job_data(self, job_raw: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Normalize raw job data to database format.

        Args:
            job_raw: Raw job data from JSON
            source: Source platform name

        Returns:
            Normalized job data dictionary
        """
        # Required fields
        title = job_raw.get('title', 'Unknown Title')
        company = job_raw.get('company', 'Unknown Company')
        url = job_raw.get('url', '')

        if not url:
            raise ValueError("Job URL is required")

        # Parse salary
        salary_min, salary_max = parse_salary(job_raw.get('salary'))

        # Generate hashes
        fuzzy_hash = generate_fuzzy_hash(company, title)

        # Determine source priority
        source_priority = determine_source_priority(source)

        # Parse posted date
        posted_date = job_raw.get('posted_date')
        scraped_at = None
        if posted_date:
            try:
                scraped_at = datetime.fromisoformat(posted_date).isoformat()
            except:
                # If parsing fails, use current time
                scraped_at = datetime.now().isoformat()
        else:
            scraped_at = datetime.now().isoformat()

        return {
            'platform': source,
            'url': url,
            'fuzzy_hash': fuzzy_hash,
            'external_id': job_raw.get('external_id'),
            'title': title,
            'company': company,
            'location': job_raw.get('location'),
            'salary_min': salary_min,
            'salary_max': salary_max,
            'salary_currency': 'USD',
            'remote_type': job_raw.get('remote_type'),
            'visa_sponsorship': job_raw.get('visa_sponsorship'),
            'easy_apply': job_raw.get('easy_apply', False),
            'jd_markdown': job_raw.get('description'),
            'jd_raw': job_raw.get('description'),
            'source': source,
            'source_priority': source_priority,
            'is_processed': False,
            'status': 'new',
            'scraped_at': scraped_at
        }

    def _get_job_by_url_hash(self, url_hash: str) -> Optional[Dict[str, Any]]:
        """Get job by URL hash.

        Args:
            url_hash: MD5 hash of URL

        Returns:
            Job dictionary or None
        """
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE url_hash = ?",
            (url_hash,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _get_job_by_fuzzy_hash(self, fuzzy_hash: str) -> Optional[Dict[str, Any]]:
        """Get job by fuzzy hash.

        Args:
            fuzzy_hash: MD5 hash of company+title

        Returns:
            Job dictionary or None
        """
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT * FROM jobs WHERE fuzzy_hash = ?",
            (fuzzy_hash,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def _update_job(self, job_id: int, job_data: Dict[str, Any]) -> None:
        """Update job with new data.

        Args:
            job_id: Job ID to update
            job_data: New job data
        """
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET title = ?, company = ?, location = ?,
                salary_min = ?, salary_max = ?, salary_currency = ?,
                remote_type = ?, visa_sponsorship = ?, easy_apply = ?,
                jd_markdown = ?, jd_raw = ?,
                source = ?, source_priority = ?,
                url = ?, fuzzy_hash = ?
            WHERE id = ?
        """, (
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
            job_data['source'],
            job_data['source_priority'],
            job_data['url'],
            job_data['fuzzy_hash'],
            job_id
        ))
        self.db.conn.commit()
        logger.debug(f"Updated job {job_id}")

    def _update_job_description(self, job_id: int, update_data: Dict[str, Any]) -> None:
        """Update only job description.

        Args:
            job_id: Job ID to update
            update_data: Data with jd_raw and jd_markdown
        """
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET jd_markdown = ?, jd_raw = ?
            WHERE id = ?
        """, (
            update_data.get('jd_markdown'),
            update_data.get('jd_raw'),
            job_id
        ))
        self.db.conn.commit()
        logger.debug(f"Updated description for job {job_id}")

"""MCP tools for importing Antigravity scraped data."""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core.importer import AntigravityImporter
from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def import_antigravity_results(files: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Import scraped job data from Antigravity JSON files.

    Args:
        files: List of file paths to import. If None, auto-detect data/*.json

    Returns:
        {
            "status": "success",
            "total_files": 3,
            "total_jobs_in_files": 145,
            "new_jobs_inserted": 120,
            "duplicates_skipped_url": 20,
            "duplicates_skipped_fuzzy": 3,
            "duplicates_updated": 2,
            "by_source": {
                "linkedin": {"total": 50, "new": 40, "url_dup": 8, "fuzzy_dup_skip": 1, "fuzzy_dup_update": 1},
                ...
            }
        }
    """
    try:
        logger.info("Starting Antigravity results import")

        # Initialize importer
        db = Database()
        importer = AntigravityImporter(db=db)

        # Import files
        stats = importer.import_multiple_files(files)

        # Format response
        return {
            "status": "success",
            "total_files": len(files) if files else len(stats.get('by_source', {})),
            "total_jobs_in_files": stats['total_jobs'],
            "new_jobs_inserted": stats['new_jobs'],
            "duplicates_skipped_url": stats['url_duplicates'],
            "duplicates_skipped_fuzzy": stats['fuzzy_duplicates_skipped'],
            "duplicates_updated": stats['fuzzy_duplicates_updated'],
            "by_source": stats['by_source'],
            "message": (
                f"Import complete: {stats['new_jobs']} new jobs inserted, "
                f"{stats['url_duplicates']} URL duplicates skipped, "
                f"{stats['fuzzy_duplicates_skipped']} fuzzy duplicates skipped, "
                f"{stats['fuzzy_duplicates_updated']} jobs updated from better sources"
            )
        }

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "JSON file(s) not found. Please check file paths."
        }

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Invalid JSON format in file. Please check file contents."
        }

    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Import failed: {str(e)}"
        }


async def list_importable_files() -> Dict[str, Any]:
    """
    List JSON files available for import in data directory.

    Returns:
        {
            "status": "success",
            "files": [
                {
                    "filename": "linkedin_scraped.json",
                    "path": "W:\\Code\\job_viewer\\data\\linkedin_scraped.json",
                    "size_kb": 125.3,
                    "job_count": 45
                }
            ]
        }
    """
    try:
        data_dir = Path("W:\\Code\\job_viewer\\data")

        if not data_dir.exists():
            return {
                "status": "success",
                "files": [],
                "message": "Data directory does not exist"
            }

        # Find JSON files
        json_files = list(data_dir.glob("*_scraped.json"))

        files_info = []
        for file_path in sorted(json_files):
            try:
                # Read file to count jobs
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    job_count = len(data) if isinstance(data, list) else 0

                files_info.append({
                    'filename': file_path.name,
                    'path': str(file_path),
                    'size_kb': round(file_path.stat().st_size / 1024, 1),
                    'job_count': job_count
                })
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")

        return {
            "status": "success",
            "files": files_info,
            "count": len(files_info),
            "message": f"Found {len(files_info)} importable JSON file(s)"
        }

    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "message": f"Failed to list files: {str(e)}"
        }


# Tool registration for MCP server
def register_tools(server):
    """
    Register importer tools with the MCP server.

    Args:
        server: MCP server instance
    """

    @server.tool()
    async def import_antigravity_results(files: list = None) -> dict:
        """
        Import scraped job data from Antigravity JSON files.

        Imports jobs with intelligent deduplication:
        - URL exact match: Skip if URL already exists
        - Fuzzy hash match: hash(company.lower() + title.lower())
          - Compare source_priority and data completeness
          - Update if new source has higher priority or more complete data

        Args:
            files: List of JSON file paths to import. If None, auto-detect data/*.json

        Returns:
            {
                "status": "success",
                "total_files": 3,
                "total_jobs_in_files": 145,
                "new_jobs_inserted": 120,
                "duplicates_skipped_url": 20,
                "duplicates_skipped_fuzzy": 3,
                "duplicates_updated": 2,
                "by_source": {
                    "linkedin": {"total": 50, "new": 40, "url_dup": 8},
                    "glassdoor": {"total": 55, "new": 45, "url_dup": 7},
                    "wellfound": {"total": 40, "new": 35, "url_dup": 5}
                }
            }
        """
        return await globals()['import_antigravity_results'](files)

    @server.tool()
    async def list_importable_files() -> dict:
        """
        List JSON files available for import.

        Returns information about JSON files in the data directory
        that can be imported, including file size and job count.

        Returns:
            {
                "status": "success",
                "files": [
                    {
                        "filename": "linkedin_scraped.json",
                        "path": "...",
                        "size_kb": 125.3,
                        "job_count": 45
                    }
                ]
            }
        """
        return await globals()['list_importable_files']()

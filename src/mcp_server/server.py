"""MCP Server for Job Hunter - Main Entry Point.

This server provides tools for autonomous job hunting workflow orchestration.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server

from src.core.database import Database
from src.core.applier import JobApplierService
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger
from src.mcp_server.tools.filter import filter_jobs_with_glm_tool
from src.mcp_server.tools.tailor import tailor_resume_tool
from src.mcp_server.tools.scraper import scrape_jobs_tool
from src.mcp_server.tools.applier import apply_to_job_tool
from src.mcp_server.tools.notifier import (
    send_telegram_notification_tool,
    send_pending_decisions_to_telegram_tool
)
from src.mcp_server.tools.antigravity import (
    generate_antigravity_scraping_guide,
    preview_antigravity_instructions,
    list_antigravity_instructions
)
from src.mcp_server.tools.importer import (
    import_antigravity_results,
    list_importable_files
)
from src.mcp_server.tools.gl_processor import (
    process_jobs_with_glm_tool
)
from src.mcp_server.tools.report import (
    generate_campaign_report_tool
)
from src.mcp_server.tools.ats_scanner import (
    scan_ats_platforms_tool
)
from src.mcp_server.tools.application import (
    generate_application_instructions_tool
)

# Initialize logger
logger = get_logger(__name__)

# Initialize server
server = Server("job-hunter")

# Initialize core components
db = Database()
config_loader = ConfigLoader()
applier_service = JobApplierService(db=db)


# =============================================================================
# TOOL STUBS - Phase 1.5 Placeholders
# =============================================================================

@server.list_tools()
async def list_tools():
    """List all available tools."""
    return [
        {
            "name": "scrape_jobs",
            "description": "Scrape jobs from job platforms (LinkedIn, Indeed, Wellfound)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform to scrape: 'all', 'linkedin', 'indeed', 'wellfound'",
                        "default": "all"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum jobs to scrape per platform",
                        "default": 100
                    },
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Search keywords (uses preferences.md target_positions if not provided)"
                    },
                    "remote_only": {
                        "type": "boolean",
                        "description": "Filter for remote-only jobs",
                        "default": True
                    }
                }
            }
        },
        {
            "name": "filter_jobs_with_glm",
            "description": "Filter jobs using GLM model for cost-effective scoring (~$0.001 per job)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum jobs to process",
                        "default": 100
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": "Jobs to process in each batch",
                        "default": 10
                    },
                    "force_refilter": {
                        "type": "boolean",
                        "description": "Re-filter already filtered jobs",
                        "default": False
                    }
                }
            }
        },
        {
            "name": "get_matched_jobs",
            "description": "Query jobs that passed filtering",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "min_score": {"type": "number", "default": 0.60},
                    "max_score": {"type": "number", "default": 1.0},
                    "status": {"type": "string", "default": "matched"},
                    "limit": {"type": "integer", "default": 20}
                }
            }
        },
        {
            "name": "check_duplicate",
            "description": "Check if a job already exists or has been applied to",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job_url": {"type": "string"},
                    "external_id": {"type": "string"},
                    "platform": {"type": "string"}
                }
            }
        },
        {
            "name": "get_pending_decisions",
            "description": "Get medium-match jobs waiting for user approval",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "process_high_match_jobs",
            "description": "Auto-apply to jobs with score >= 0.85",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "approve_job",
            "description": "User approves a job for application",
            "inputSchema": {
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "integer"}
                }
            }
        },
        {
            "name": "skip_job",
            "description": "User skips a job",
            "inputSchema": {
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "integer"},
                    "reason": {"type": "string"}
                }
            }
        },
        {
            "name": "tailor_resume",
            "description": "Generate customized resume for a specific job",
            "inputSchema": {
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "integer"}
                }
            }
        },
        {
            "name": "apply_to_job",
            "description": "Submit a job application",
            "inputSchema": {
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "integer"},
                    "resume_path": {"type": "string"}
                }
            }
        },
        {
            "name": "send_telegram_notification",
            "description": "Send a message via Telegram",
            "inputSchema": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"},
                    "parse_mode": {"type": "string", "default": "Markdown"}
                }
            }
        },
        {
            "name": "send_pending_decisions_to_telegram",
            "description": "Send pending jobs to user for decision",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "get_run_summary",
            "description": "Get statistics for the current run",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "generate_antigravity_scraping_guide",
            "description": "Generate Antigravity scraping instructions from preferences and credentials",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "preview_antigravity_instructions",
            "description": "Preview Antigravity instructions without generating files",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "list_antigravity_instructions",
            "description": "List all generated Antigravity instruction files",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "import_antigravity_results",
            "description": "Import scraped job data from Antigravity JSON files with intelligent deduplication",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of JSON file paths. If not provided, auto-detect data/*.json"
                    }
                }
            }
        },
        {
            "name": "list_importable_files",
            "description": "List JSON files available for import in data directory",
            "inputSchema": {"type": "object", "properties": {}}
        },
        {
            "name": "process_jobs_with_glm",
            "description": "Process unfiltered jobs with GLM three-tier filtering system (≥85: resume, 60-84: report, <60: archive)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "batch_size": {
                        "type": "integer",
                        "description": "Number of jobs to process in parallel",
                        "default": 20
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of jobs to process (None = all)",
                        "default": None
                    },
                    "enable_semantic_dedup": {
                        "type": "boolean",
                        "description": "Enable semantic duplicate detection",
                        "default": True
                    },
                    "enable_tier1_resume": {
                        "type": "boolean",
                        "description": "Auto-generate resumes for Tier 1 jobs",
                        "default": True
                    }
                }
            }
        },
        {
            "name": "generate_campaign_report",
            "description": "Generate daily campaign report with HIGH/MEDIUM match job tables",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today."
                    }
                }
            }
        },
        {
            "name": "scan_ats_platforms",
            "description": "Scan ATS platforms (Greenhouse, Lever, Ashby, Workable) via Google dorking. Automated, no Antigravity needed.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "job_titles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Job titles to search. Defaults from preferences.md"
                    },
                    "max_results_per_platform": {
                        "type": "integer",
                        "description": "Max results per platform per title",
                        "default": 50
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional location filter (e.g., 'Remote', 'New York')"
                    }
                }
            }
        },
        {
            "name": "generate_application_instructions",
            "description": "Generate Antigravity instructions for auto-applying to approved jobs with platform-specific form filling",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "campaign_date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format. Defaults to today."
                    }
                }
            }
        }
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls with placeholder implementations."""
    
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        # All tools return placeholder responses in Phase 1.5
        if name == "scrape_jobs":
            # Phase 2 - IMPLEMENTED
            platform = arguments.get("platform", "all")
            limit = arguments.get("limit", 100)
            keywords = arguments.get("keywords")
            remote_only = arguments.get("remote_only", True)

            result = await scrape_jobs_tool(
                platform=platform,
                limit=limit,
                keywords=keywords,
                remote_only=remote_only
            )

            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]
        
        elif name == "filter_jobs_with_glm":
            # Phase 3 - IMPLEMENTED
            limit = arguments.get("limit", 100)
            batch_size = arguments.get("batch_size", 10)
            force_refilter = arguments.get("force_refilter", False)
            
            result = await filter_jobs_with_glm_tool(limit, batch_size, force_refilter)
            return [{"content": result}]
        
        elif name == "get_matched_jobs":
            # This one can work with existing database
            min_score = arguments.get("min_score", 0.60)
            max_score = arguments.get("max_score", 1.0)
            status = arguments.get("status", "matched")
            limit = arguments.get("limit", 20)
            
            jobs = db.get_matched_jobs(min_score, max_score, status, limit)
            
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "status": "success",
                        "total": len(jobs),
                        "jobs": [
                            {
                                "id": job.id,
                                "title": job.title,
                                "company": job.company,
                                "match_score": job.match_score,
                                "url": job.url
                            }
                            for job in jobs
                        ]
                    }, indent=2)
                }]
            }]
        
        elif name == "check_duplicate":
            # This can work with existing database
            result = db.check_duplicate(
                platform=arguments.get("platform"),
                external_id=arguments.get("external_id"),
                url=arguments.get("job_url")
            )
            
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]
        
        elif name == "get_pending_decisions":
            # Get jobs that need user decision
            # These are jobs with status='matched' and decision_type='manual'
            # (i.e., match_score between 0.60-0.85)
            jobs = db.get_matched_jobs(
                min_score=0.60,
                max_score=0.85,
                status="matched",
                limit=100
            )

            # Filter to only those with decision_type='manual' and not already decided
            pending_jobs = [
                job for job in jobs
                if job.decision_type == 'manual' and job.decided_at is None
            ]

            # Format job details for response
            jobs_data = []
            for job in pending_jobs:
                job_dict = {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "url": job.url,
                    "platform": job.platform,
                    "match_score": round(job.match_score, 2) if job.match_score else None,
                    "match_reasoning": job.match_reasoning,
                    "key_requirements": job.key_requirements,
                    "red_flags": job.red_flags,
                    "salary_range": None,
                    "remote_type": job.remote_type,
                    "visa_sponsorship": job.visa_sponsorship,
                    "easy_apply": job.easy_apply
                }

                # Format salary range if available
                if job.salary_min or job.salary_max:
                    if job.salary_min and job.salary_max:
                        job_dict["salary_range"] = f"${job.salary_min//1000}k-${job.salary_max//1000}k {job.salary_currency}"
                    elif job.salary_min:
                        job_dict["salary_range"] = f"${job.salary_min//1000}k+ {job.salary_currency}"
                    elif job.salary_max:
                        job_dict["salary_range"] = f"Up to ${job.salary_max//1000}k {job.salary_currency}"

                jobs_data.append(job_dict)

            # Sort by match score descending
            jobs_data.sort(key=lambda x: x.get("match_score", 0), reverse=True)

            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "status": "success",
                        "count": len(jobs_data),
                        "jobs": jobs_data
                    }, indent=2)
                }]
            }]
        
        elif name == "process_high_match_jobs":
            # Auto-apply to jobs with score >= 0.85
            logger.info("Processing high match jobs (auto-apply for score >= 0.85)")

            # Query high match jobs
            jobs = db.get_matched_jobs(
                min_score=0.85,
                max_score=1.0,
                status="matched",
                limit=100
            )

            # Filter to only auto-apply jobs that haven't been decided yet
            auto_jobs = [
                job for job in jobs
                if job.decision_type == 'auto' and job.decided_at is None
            ]

            logger.info(f"Found {len(auto_jobs)} high-match jobs for auto-apply")

            # Statistics
            processed = 0
            applied = 0
            failed = 0
            skipped = 0
            details = []

            # Process each job
            for job in auto_jobs:
                processed += 1
                logger.info(f"Processing job {job.id}: {job.title} at {job.company}")

                try:
                    # Generate tailored resume
                    logger.debug(f"Generating tailored resume for job {job.id}")
                    resume_result = await tailor_resume_tool(job.id)

                    # Parse resume result
                    resume_data = json.loads(resume_result[0].text)

                    if not resume_data.get("success"):
                        logger.error(f"Resume tailoring failed for job {job.id}: {resume_data.get('error')}")
                        failed += 1
                        details.append({
                            "job_id": job.id,
                            "company": job.company,
                            "title": job.title,
                            "result": "failed",
                            "error": f"Resume tailoring failed: {resume_data.get('error')}"
                        })
                        continue

                    resume_path = resume_data.get("pdf_path")
                    logger.debug(f"Resume generated: {resume_path}")

                    # Apply to job
                    logger.debug(f"Applying to job {job.id}")
                    application_result = await applier_service.apply_to_job(
                        job_id=job.id,
                        resume_path=resume_path
                    )

                    if application_result.success:
                        logger.info(f"Successfully applied to job {job.id}")
                        applied += 1
                        details.append({
                            "job_id": job.id,
                            "company": job.company,
                            "title": job.title,
                            "result": "applied",
                            "error": None
                        })
                    elif application_result.method == "skipped":
                        logger.warning(f"Job {job.id} skipped: {application_result.error}")
                        skipped += 1
                        details.append({
                            "job_id": job.id,
                            "company": job.company,
                            "title": job.title,
                            "result": "skipped",
                            "error": application_result.error
                        })
                    else:
                        logger.error(f"Application failed for job {job.id}: {application_result.error}")
                        failed += 1
                        details.append({
                            "job_id": job.id,
                            "company": job.company,
                            "title": job.title,
                            "result": "failed",
                            "error": application_result.error
                        })

                except Exception as e:
                    logger.error(f"Error processing job {job.id}: {e}", exc_info=True)
                    failed += 1
                    details.append({
                        "job_id": job.id,
                        "company": job.company,
                        "title": job.title,
                        "result": "failed",
                        "error": str(e)
                    })

            # Determine overall status
            if processed == 0:
                status = "success"
            elif failed == 0:
                status = "success"
            elif applied > 0:
                status = "partial"
            else:
                status = "error"

            result = {
                "status": status,
                "processed": processed,
                "applied": applied,
                "failed": failed,
                "skipped": skipped,
                "details": details
            }

            logger.info(
                f"Auto-apply complete: {processed} processed, "
                f"{applied} applied, {failed} failed, {skipped} skipped"
            )

            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]
        
        elif name == "approve_job":
            # User approves a job for application
            job_id = arguments.get("job_id")

            if not job_id:
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "status": "error",
                            "error": "job_id is required"
                        })
                    }],
                    "isError": True
                }]

            logger.info(f"Approving job {job_id} for application")

            try:
                # Get job by ID and validate
                job = db.get_job_by_id(job_id)
                if not job:
                    return [{
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "status": "error",
                                "error": f"Job {job_id} not found"
                            })
                        }],
                        "isError": True
                    }]

                # Validate job is in pending state
                if job.status != "matched":
                    logger.warning(
                        f"Job {job_id} is not in 'matched' status (current: {job.status})"
                    )

                # Update job status to approved
                db.update_job_status(job_id, "approved")
                logger.info(f"Job {job_id} marked as approved")

                # Generate tailored resume
                logger.debug(f"Generating tailored resume for job {job_id}")
                resume_result = await tailor_resume_tool(job_id)
                resume_data = json.loads(resume_result[0].text)

                if not resume_data.get("success"):
                    error_msg = resume_data.get("error", "Unknown error")
                    logger.error(f"Resume tailoring failed for job {job_id}: {error_msg}")

                    return [{
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "status": "error",
                                "job_id": job_id,
                                "error": f"Resume tailoring failed: {error_msg}"
                            })
                        }],
                        "isError": True
                    }]

                resume_path = resume_data.get("pdf_path")
                logger.debug(f"Resume generated: {resume_path}")

                # Apply to job
                logger.debug(f"Applying to job {job_id}")
                application_result = await applier_service.apply_to_job(
                    job_id=job_id,
                    resume_path=resume_path
                )

                # Format result
                if application_result.success:
                    logger.info(f"Successfully applied to job {job_id}")
                    result = {
                        "status": "success",
                        "job_id": job_id,
                        "resume_path": resume_path,
                        "application_result": {
                            "submitted": True,
                            "error": None
                        }
                    }
                else:
                    logger.error(
                        f"Application failed for job {job_id}: {application_result.error}"
                    )
                    result = {
                        "status": "error",
                        "job_id": job_id,
                        "resume_path": resume_path,
                        "application_result": {
                            "submitted": False,
                            "error": application_result.error
                        }
                    }

                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }]
                }]

            except Exception as e:
                logger.error(f"Error approving job {job_id}: {e}", exc_info=True)
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "status": "error",
                            "job_id": job_id,
                            "error": str(e)
                        })
                    }],
                    "isError": True
                }]
        
        elif name == "skip_job":
            # User skips a job
            job_id = arguments.get("job_id")
            reason = arguments.get("reason")

            if not job_id:
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "status": "error",
                            "error": "job_id is required"
                        })
                    }],
                    "isError": True
                }]

            logger.info(f"Skipping job {job_id}" + (f" (reason: {reason})" if reason else ""))

            try:
                # Get job by ID and validate it exists
                job = db.get_job_by_id(job_id)
                if not job:
                    return [{
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "status": "error",
                                "error": f"Job {job_id} not found"
                            })
                        }],
                        "isError": True
                    }]

                # Update job status to skipped
                # The decided_at timestamp will be set automatically by update_job_status
                db.update_job_status(job_id, "skipped")

                # Store skip reason if provided (log it to database logs)
                if reason:
                    db.log(
                        level="info",
                        component="decision",
                        message=f"Job {job_id} skipped by user",
                        details={
                            "job_id": job_id,
                            "company": job.company,
                            "title": job.title,
                            "reason": reason
                        }
                    )

                logger.info(f"Job {job_id} marked as skipped")

                result = {
                    "status": "success",
                    "job_id": job_id
                }

                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }]
                }]

            except Exception as e:
                logger.error(f"Error skipping job {job_id}: {e}", exc_info=True)
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "status": "error",
                            "job_id": job_id,
                            "error": str(e)
                        })
                    }],
                    "isError": True
                }]
        
        elif name == "tailor_resume":
            # Phase 4 - IMPLEMENTED
            job_id = arguments.get("job_id")
            if not job_id:
                return [{"content": [{"type": "text", "text": json.dumps({"success": False, "error": "job_id is required"})}]}]
            
            result = await tailor_resume_tool(job_id)
            return [{"content": result}]
        
        elif name == "apply_to_job":
            # Phase 5 - IMPLEMENTED
            job_id = arguments.get("job_id")
            resume_path = arguments.get("resume_path")

            if not job_id:
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "error": "job_id is required"
                        })
                    }]
                }]

            result = await apply_to_job_tool(job_id, resume_path)
            return [{"content": result}]
        
        elif name == "send_telegram_notification":
            # Phase 6 - IMPLEMENTED
            message = arguments.get("message")
            parse_mode = arguments.get("parse_mode", "Markdown")
            
            if not message:
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "status": "error",
                            "error": "message is required"
                        })
                    }]
                }]
            
            result = await send_telegram_notification_tool(message, parse_mode)
            return [{"content": result}]
        
        elif name == "send_pending_decisions_to_telegram":
            # Phase 6 - IMPLEMENTED
            result = await send_pending_decisions_to_telegram_tool()
            return [{"content": result}]
        
        elif name == "get_run_summary":
            # This can partially work with existing database
            current_run = db.get_current_run()
            if current_run:
                return [{
                    "content": [{
                        "type": "text",
                        "text": json.dumps(current_run, indent=2)
                    }]
                }]
            else:
                return _stub_response(
                    "get_run_summary",
                    "No active run",
                    {"status": "no_active_run"}
                )

        elif name == "generate_antigravity_scraping_guide":
            # Antigravity instruction generator
            result = await generate_antigravity_scraping_guide()
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "preview_antigravity_instructions":
            # Preview Antigravity instructions
            result = await preview_antigravity_instructions()
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "list_antigravity_instructions":
            # List generated instruction files
            result = await list_antigravity_instructions()
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "import_antigravity_results":
            # Import Antigravity scraped data
            files = arguments.get("files")
            result = await import_antigravity_results(files)
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "list_importable_files":
            # List importable JSON files
            result = await list_importable_files()
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "process_jobs_with_glm":
            # Process unfiltered jobs with GLM three-tier system
            batch_size = arguments.get("batch_size", 20)
            limit = arguments.get("limit", None)
            enable_semantic_dedup = arguments.get("enable_semantic_dedup", True)
            enable_tier1_resume = arguments.get("enable_tier1_resume", True)

            result = await process_jobs_with_glm_tool(
                batch_size=batch_size,
                limit=limit,
                enable_semantic_dedup=enable_semantic_dedup,
                enable_tier1_resume=enable_tier1_resume
            )
            return [{"content": result}]

        elif name == "generate_campaign_report":
            # Generate daily campaign report
            date = arguments.get("date")
            result = await generate_campaign_report_tool(date)
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "scan_ats_platforms":
            # Scan ATS platforms via Google dorking
            job_titles = arguments.get("job_titles")
            max_results = arguments.get("max_results_per_platform", 50)
            location = arguments.get("location")
            result = await scan_ats_platforms_tool(
                job_titles=job_titles,
                max_results_per_platform=max_results,
                location=location
            )
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        elif name == "generate_application_instructions":
            # Generate Antigravity application instructions
            campaign_date = arguments.get("campaign_date")
            result = await generate_application_instructions_tool(campaign_date)
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }]
            }]

        else:
            return [{
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "status": "error",
                        "error": f"Unknown tool: {name}"
                    })
                }],
                "isError": True
            }]
    
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}", exc_info=True)
        return [{
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "error",
                    "error": str(e)
                })
            }],
            "isError": True
        }]


def _stub_response(tool_name: str, implementation_phase: str, data: dict):
    """Create a placeholder response for unimplemented tools."""
    return [{
        "content": [{
            "type": "text",
            "text": json.dumps({
                **data,
                "note": f"🚧 {tool_name} is a placeholder. {implementation_phase}."
            }, indent=2)
        }]
    }]


# =============================================================================
# RESOURCE HANDLERS
# =============================================================================

@server.list_resources()
async def list_resources():
    """List all available resources."""
    return [
        {
            "uri": "resume://current",
            "name": "Current Resume",
            "description": "User's resume from config/resume.md",
            "mimeType": "text/markdown"
        },
        {
            "uri": "preferences://config",
            "name": "Job Preferences",
            "description": "User's job search preferences from config/preferences.md",
            "mimeType": "text/markdown"
        },
        {
            "uri": "achievements://list",
            "name": "Achievements Pool",
            "description": "User's achievements from config/achievements.md",
            "mimeType": "text/markdown"
        },
        {
            "uri": "jobs://pending",
            "name": "Pending Jobs",
            "description": "Jobs awaiting user decision",
            "mimeType": "application/json"
        },
        {
            "uri": "credentials://config",
            "name": "Platform Credentials",
            "description": "Credentials for job platforms and APIs from config/credentials.md",
            "mimeType": "application/json"
        }
    ]


@server.read_resource()
async def read_resource(uri: str):
    """Read resource content."""
    
    logger.info(f"Resource requested: {uri}")
    
    try:
        if uri == "resume://current":
            path = Path("config/resume.md")
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return [{
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content
                }]
            else:
                return [{
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "⚠️ Resume file not found. Copy config/resume.example.md to config/resume.md and fill in your information."
                }]
        
        elif uri == "preferences://config":
            path = Path("config/preferences.md")
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return [{
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content
                }]
            else:
                return [{
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "⚠️ Preferences file not found. Copy config/preferences.example.md to config/preferences.md and fill in your preferences."
                }]
        
        elif uri == "achievements://list":
            path = Path("config/achievements.md")
            if path.exists():
                content = path.read_text(encoding="utf-8")
                return [{
                    "uri": uri,
                    "mimeType": "text/markdown",
                    "text": content
                }]
            else:
                return [{
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "⚠️ Achievements file not found. Copy config/achievements.example.md to config/achievements.md and list your achievements."
                }]
        
        elif uri == "jobs://pending":
            # Get pending jobs from database
            jobs = db.get_jobs_by_status("pending_decision", limit=50)
            
            jobs_data = [
                {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "match_score": job.match_score,
                    "match_reasoning": job.match_reasoning,
                    "url": job.url
                }
                for job in jobs
            ]
            
            return [{
                "uri": uri,
                "mimeType": "application/json",
                "text": json.dumps(jobs_data, indent=2)
            }]

        elif uri == "credentials://config":
            path = Path("config/credentials.md")
            if path.exists():
                try:
                    credentials = config_loader.get_credentials()

                    # Build JSON response with credentials
                    credentials_data = {
                        "platforms": {
                            name: {
                                "platform": cred.platform,
                                "email": cred.email,
                                "password": cred.password
                            }
                            for name, cred in credentials.platforms.items()
                        },
                        "apis": {
                            name: {
                                "service": cred.service,
                                "api_key": cred.api_key,
                                "api_url": cred.api_url,
                                **({"extra": cred.extra} if cred.extra else {})
                            }
                            for name, cred in credentials.apis.items()
                        }
                    }

                    logger.debug(f"Loaded credentials for {len(credentials.platforms)} platforms and {len(credentials.apis)} APIs")

                    return [{
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(credentials_data, indent=2)
                    }]
                except Exception as e:
                    logger.error(f"Failed to parse credentials: {e}")
                    return [{
                        "uri": uri,
                        "mimeType": "text/plain",
                        "text": f"Error parsing credentials.md: {str(e)}"
                    }]
            else:
                return [{
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": "⚠️ Credentials file not found. Copy config/credentials.example.md to config/credentials.md and fill in your credentials."
                }]

        else:
            return [{
                "uri": uri,
                "mimeType": "text/plain",
                "text": f"Unknown resource: {uri}"
            }]
    
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}", exc_info=True)
        return [{
            "uri": uri,
            "mimeType": "text/plain",
            "text": f"Error reading resource: {str(e)}"
        }]


# =============================================================================
# SERVER MAIN
# =============================================================================

async def main():
    """Run the MCP server."""
    logger.info("Starting Job Hunter MCP Server...")
    
    # Initialize database schema if needed
    try:
        db.init_schema()
        logger.info("Database schema initialized")
    except Exception as e:
        logger.warning(f"Database already initialized or error: {e}")
    
    # Log server info
    logger.info("=" * 60)
    logger.info("Job Hunter MCP Server")
    logger.info("=" * 60)
    logger.info("Server name: job-hunter")
    logger.info("Tools: 13 registered (12 stubs + 1 basic)")
    logger.info("Resources: 5 registered")
    logger.info("Database: Connected")
    logger.info("=" * 60)
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

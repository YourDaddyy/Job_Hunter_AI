"""
Campaign Report Generator

Generates Markdown daily campaign reports with HIGH/MEDIUM match job tables.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.database import Database
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CampaignReportGenerator:
    """
    Generates daily campaign reports showing matched jobs.
    
    Reports include:
    - HIGH MATCH JOBS (Tier 1, score ≥85) - Resumes already generated
    - MEDIUM MATCH JOBS (Tier 2, 60≤score<85) - Awaiting user decision
    - Statistics and cost breakdown
    """
    
    def __init__(self, db: Optional[Database] = None):
        """Initialize the report generator.
        
        Args:
            db: Database instance. Creates new one if not provided.
        """
        self.db = db or Database()
        self.output_dir = Path("campaigns")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_report(self, date: Optional[str] = None) -> dict:
        """
        Generate campaign report for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format. Defaults to today.
            
        Returns:
            dict with report_path, high_match_count, medium_match_count
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Generating campaign report for {date}")
        
        # Query database for matched jobs
        high_match = self._get_high_match_jobs(date)
        medium_match = self._get_medium_match_jobs(date)
        
        # Get statistics
        total_processed = self._get_total_processed(date)
        total_rejected = self._get_total_rejected(date)
        
        # Generate markdown content
        markdown = self._generate_markdown(
            high_match=high_match,
            medium_match=medium_match,
            total_processed=total_processed,
            total_rejected=total_rejected,
            date=date
        )
        
        # Save to file
        output_path = self.output_dir / f"campaign_{date}.md"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        
        logger.info(f"Report saved to {output_path}")
        
        return {
            "report_path": str(output_path),
            "high_match_count": len(high_match),
            "medium_match_count": len(medium_match),
            "total_processed": total_processed,
            "total_rejected": total_rejected
        }
    
    def _get_high_match_jobs(self, date: str) -> list:
        """Get HIGH match jobs (decision_type='auto')."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, company, title, match_score as ai_score, match_reasoning as ai_reasoning, url, source
            FROM jobs
            WHERE status = 'matched'
            AND decision_type = 'auto'
            AND DATE(scraped_at) = ?
            ORDER BY match_score DESC
        """, (date,))

        # Convert rows to dictionaries
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_medium_match_jobs(self, date: str) -> list:
        """Get MEDIUM match jobs (decision_type='manual')."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, company, title, match_score as ai_score, match_reasoning as ai_reasoning, url, source
            FROM jobs
            WHERE status = 'matched'
            AND decision_type = 'manual'
            AND DATE(scraped_at) = ?
            ORDER BY match_score DESC
        """, (date,))

        # Convert rows to dictionaries
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _get_total_processed(self, date: str) -> int:
        """Get total jobs processed on date."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE is_processed = 1
            AND DATE(scraped_at) = ?
        """, (date,))
        result = cursor.fetchone()
        return result[0] if result else 0

    def _get_total_rejected(self, date: str) -> int:
        """Get total rejected jobs on date."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE status = 'rejected'
            AND DATE(scraped_at) = ?
        """, (date,))
        result = cursor.fetchone()
        return result[0] if result else 0
    
    def _generate_markdown(
        self,
        high_match: list,
        medium_match: list,
        total_processed: int,
        total_rejected: int,
        date: str
    ) -> str:
        """Generate the Markdown report content."""
        
        # Calculate estimated cost
        glm_cost = total_processed * 0.001  # $0.001 per job
        resume_cost = len(high_match) * 0.02  # $0.02 per resume
        total_cost = glm_cost + resume_cost
        
        md = f"""# Application Queue ({date})

> Generated by Job Hunter AI

---

## 🎯 HIGH MATCH JOBS (Resumes Ready) ✓

These jobs scored ≥85 and have tailored resumes already generated.

"""
        
        if high_match:
            md += "| Status | Score | Company | Role | Source | Resume | Apply |\n"
            md += "|--------|-------|---------|------|--------|--------|-------|\n"
            
            for job in high_match:
                company = job['company']
                title = job['title']
                # Convert score from 0-1 range to 0-100 percentage
                score = int(job['ai_score'] * 100) if job['ai_score'] else 0
                url = job['url']
                source = job['source'] or 'unknown'

                # Generate resume filename
                safe_company = company.replace(' ', '_').replace('/', '-')[:20]
                safe_title = title.replace(' ', '_').replace('/', '-')[:20]
                resume_path = f"output/{safe_company}_{safe_title}.pdf"

                md += f"| [ ] | {score} | {company} | {title} | {source} | [PDF]({resume_path}) | [Apply]({url}) |\n"
            
            md += f"\n**→ {len(high_match)} jobs ready to apply!** Resumes already customized.\n"
        else:
            md += "*No high match jobs found today.*\n"
        
        md += f"""
---

## ⚠️ MEDIUM MATCH JOBS (Need Your Decision)

These jobs scored 60-84. Review and approve the ones you want to apply to.

"""
        
        if medium_match:
            md += "| Score | Company | Role | Source | Why Medium? | Action |\n"
            md += "|-------|---------|------|--------|-------------|--------|\n"
            
            for job in medium_match:
                company = job['company']
                title = job['title']
                # Convert score from 0-1 range to 0-100 percentage
                score = int(job['ai_score'] * 100) if job['ai_score'] else 0
                url = job['url']
                source = job['source'] or 'unknown'
                reasoning = job['ai_reasoning'] or ''

                # Truncate reasoning
                reason_short = reasoning[:80] + "..." if len(reasoning) > 80 else reasoning
                reason_short = reason_short.replace('|', '\\|').replace('\n', ' ')

                md += f"| {score} | {company} | {title} | {source} | {reason_short} | [View]({url}) |\n"
            
            md += f"\n**→ {len(medium_match)} jobs awaiting your review.**\n"
        else:
            md += "*No medium match jobs found today.*\n"
        
        md += f"""
---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Total jobs processed | {total_processed} |
| High match (≥85) | {len(high_match)} |
| Medium match (60-84) | {len(medium_match)} |
| Rejected (<60) | {total_rejected} |
| **Estimated cost** | **${total_cost:.2f}** |

### Cost Breakdown
- GLM filtering: ${glm_cost:.2f} ({total_processed} jobs × $0.001)
- Resume generation: ${resume_cost:.2f} ({len(high_match)} resumes × $0.02)

---

## 📝 Next Steps

1. **Apply to HIGH match jobs** - Resumes are ready in `output/`
2. **Review MEDIUM match jobs** - Approve ones you want
3. **Run application generator** - `generate_application_instructions()`

---

*Generated by Job Hunter AI* | {date}
"""
        
        return md


# CLI support for testing
if __name__ == "__main__":
    import sys
    
    date = sys.argv[1] if len(sys.argv) > 1 else None
    generator = CampaignReportGenerator()
    result = generator.generate_report(date)
    
    print(f"Report generated: {result['report_path']}")
    print(f"  High match: {result['high_match_count']}")
    print(f"  Medium match: {result['medium_match_count']}")

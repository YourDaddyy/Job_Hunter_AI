"""
Application Guide Generator

Generates JSON instructions for Antigravity to auto-apply to approved jobs.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.core.database import Database
from src.utils.config import ConfigLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ApplicationGuideGenerator:
    """
    Generates Antigravity application instructions for approved jobs.
    
    Creates JSON files that guide Antigravity browser agent through:
    - Navigating to job application pages
    - Filling form fields with user data
    - Uploading tailored resumes
    - Pausing before final submit for user review
    """
    
    def __init__(
        self,
        db: Optional[Database] = None,
        config_loader: Optional[ConfigLoader] = None
    ):
        """Initialize the application guide generator.
        
        Args:
            db: Database instance
            config_loader: Config loader for credentials
        """
        self.db = db or Database()
        self.config_loader = config_loader or ConfigLoader()
        self.output_dir = Path("instructions")
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_application_guide(
        self,
        campaign_date: Optional[str] = None
    ) -> dict:
        """
        Generate application instructions for approved jobs.
        
        Args:
            campaign_date: Date in YYYY-MM-DD format. Defaults to today.
            
        Returns:
            dict with instruction_file, applications_count, etc.
        """
        if not campaign_date:
            campaign_date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"Generating application guide for {campaign_date}")
        
        # Get approved jobs
        high_match = self._get_high_match_jobs(campaign_date)
        medium_approved = self._get_approved_medium_jobs(campaign_date)
        
        all_approved = high_match + medium_approved
        
        if not all_approved:
            logger.warning("No approved jobs found for application guide")
            return {
                "status": "no_jobs",
                "instruction_file": None,
                "applications_count": 0,
                "message": "No approved jobs found. Run GLM filtering first."
            }
        
        # Load credentials for form filling
        credentials_obj = self.config_loader.get_credentials()
        resume_obj = self.config_loader.get_resume()
        
        # Generate instructions for each job
        applications = []
        for job_obj in all_approved:
            # Convert Job dataclass to dict
            job = {
                'id': job_obj.id,
                'company': job_obj.company,
                'title': job_obj.title,
                'url': job_obj.url,
                'source': job_obj.source,
                'match_score': job_obj.match_score or 0
            }

            app_instruction = {
                "job_id": job['id'],
                "company": job['company'],
                "title": job['title'],
                "url": job['url'],
                "source": job.get('source', 'unknown'),
                "score": int(job.get('match_score', 0) * 100),  # Convert 0-1 to 0-100
                "resume_path": self._get_resume_path(job),
                "instructions": self._generate_form_instructions(job, resume_obj.personal_info),
                "platform_type": self._detect_platform_type(job['url']),
                "pause_before_submit": True,  # Safety: User review before submit
                "rate_limit_seconds": 300  # 5 min between applications
            }
            applications.append(app_instruction)
        
        # Create instruction file
        instruction_file = {
            "_metadata": {
                "generated_at": datetime.now().isoformat(),
                "task_type": "apply_to_jobs",
                "campaign_date": campaign_date,
                "version": "1.0"
            },
            "user_info": {
                "name": resume_obj.personal_info.name,
                "email": resume_obj.personal_info.email,
                "phone": resume_obj.personal_info.phone,
                "linkedin_url": resume_obj.personal_info.linkedin or ''
            },
            "applications": applications,
            "rate_limit": {
                "max_applications_per_hour": 5,
                "delay_between_applications_seconds": 300
            },
            "safety": {
                "pause_before_submit": True,
                "user_confirmation_required": True,
                "max_applications_per_day": 20
            }
        }
        
        # Save to file
        output_path = self.output_dir / f"apply_jobs_{campaign_date}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(instruction_file, f, indent=2)
        
        logger.info(f"Application guide saved to {output_path}")
        
        return {
            "status": "success",
            "instruction_file": str(output_path),
            "applications_count": len(applications),
            "high_match": len(high_match),
            "medium_approved": len(medium_approved),
            "message": f"Generated instructions for {len(applications)} jobs. "
                      f"Run: antigravity run {output_path}"
        }
    
    def _get_high_match_jobs(self, date: str) -> list:
        """Get HIGH match jobs (decision_type='auto')."""
        # Use get_matched_jobs with high threshold (≥85% = 0.85)
        all_matched = self.db.get_matched_jobs(
            min_score=0.85,
            max_score=1.0,
            status="matched",
            limit=100
        )

        # Filter by date and decision_type
        result = []
        for job in all_matched:
            # Check if job has decision_type='auto' and matches the date
            if job.decision_type == 'auto':
                # Parse date from scraped_at timestamp
                job_date = job.scraped_at.strftime('%Y-%m-%d') if job.scraped_at else None
                if job_date == date:
                    result.append(job)

        return result
    
    def _get_approved_medium_jobs(self, date: str) -> list:
        """Get approved MEDIUM match jobs."""
        # Use get_jobs_by_status to get approved jobs
        all_approved = self.db.get_jobs_by_status(status="approved", limit=100)

        # Filter by date and score range (60-84% = 0.60-0.84)
        result = []
        for job in all_approved:
            # Check score is in medium range
            if job.match_score and 0.60 <= job.match_score < 0.85:
                # Parse date from scraped_at timestamp
                job_date = job.scraped_at.strftime('%Y-%m-%d') if job.scraped_at else None
                if job_date == date:
                    result.append(job)

        return result
    
    def _get_resume_path(self, job: dict) -> str:
        """Generate resume path for job."""
        company = job['company'].replace(' ', '_').replace('/', '-')[:20]
        title = job['title'].replace(' ', '_').replace('/', '-')[:20]
        return f"output/{company}_{title}.pdf"
    
    def _detect_platform_type(self, url: str) -> str:
        """Detect application platform type from URL."""
        url_lower = url.lower()
        
        if 'greenhouse.io' in url_lower:
            return 'greenhouse'
        elif 'lever.co' in url_lower:
            return 'lever'
        elif 'ashbyhq.com' in url_lower:
            return 'ashby'
        elif 'workable.com' in url_lower:
            return 'workable'
        elif 'linkedin.com' in url_lower:
            return 'linkedin'
        elif 'indeed.com' in url_lower:
            return 'indeed'
        elif 'glassdoor.com' in url_lower:
            return 'glassdoor'
        else:
            return 'generic'
    
    def _generate_form_instructions(
        self,
        job: dict,
        personal_info
    ) -> str:
        """
        Generate natural language instructions for form filling.

        Platform-specific instructions based on URL.
        """
        url = job['url']
        resume_path = self._get_resume_path(job)
        platform = self._detect_platform_type(url)

        # Common fields
        name = personal_info.name
        email = personal_info.email
        phone = personal_info.phone
        linkedin = personal_info.linkedin or ''
        
        if platform == 'greenhouse':
            return f"""
1. Navigate to {url}
2. Click "Apply" or "Submit Application" button
3. Fill form fields:
   - First Name: {name.split()[0] if ' ' in name else name}
   - Last Name: {name.split()[-1] if ' ' in name else ''}
   - Email: {email}
   - Phone: {phone}
   - Resume: Upload file "{resume_path}"
   - LinkedIn: {linkedin}
4. Answer any screening questions (use best judgment or skip optional)
5. **PAUSE at Submit button** - Wait for user confirmation
"""
        
        elif platform == 'lever':
            return f"""
1. Navigate to {url}
2. Click "Apply for this job" button
3. Fill form fields:
   - Full Name: {name}
   - Email: {email}
   - Phone: {phone}
   - Resume: Upload file "{resume_path}"
   - Additional Information: "Please see my resume for detailed experience"
4. **PAUSE at Submit button** - Wait for user confirmation
"""
        
        elif platform == 'ashby':
            return f"""
1. Navigate to {url}
2. Click "Apply" button
3. Fill form fields:
   - Name: {name}
   - Email: {email}
   - Phone: {phone}
   - Resume: Upload file "{resume_path}"
4. Answer any required questions
5. **PAUSE at Submit button** - Wait for user confirmation
"""
        
        elif platform == 'workable':
            return f"""
1. Navigate to {url}
2. Click "Apply" button
3. Fill form fields:
   - Full Name: {name}
   - Email: {email}
   - Phone: {phone}
   - Resume: Upload file "{resume_path}"
4. Fill any additional required fields
5. **PAUSE at Submit button** - Wait for user confirmation
"""
        
        elif platform == 'linkedin':
            return f"""
1. Navigate to {url}
2. Click "Easy Apply" button (if available) or "Apply" button
3. For Easy Apply:
   - Resume: Upload file "{resume_path}"
   - Answer screening questions
   - Step through wizard
4. For External Apply:
   - Fill form on company website
   - Use Email: {email}, Phone: {phone}
5. **PAUSE at final Submit/Review step** - Wait for user confirmation
"""
        
        else:  # Generic / other platforms
            return f"""
1. Navigate to {url}
2. Look for "Apply" or "Submit Application" button
3. Fill standard form fields:
   - Name: {name}
   - Email: {email}
   - Phone: {phone}
   - Resume: Upload file "{resume_path}"
4. Complete any additional required fields
5. **PAUSE before final submit** - Wait for user confirmation
"""


# CLI support for testing
if __name__ == "__main__":
    import sys
    
    date = sys.argv[1] if len(sys.argv) > 1 else None
    generator = ApplicationGuideGenerator()
    result = generator.generate_application_guide(date)
    
    print(f"Result: {result}")

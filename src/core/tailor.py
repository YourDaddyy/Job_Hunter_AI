"""Resume tailoring service using Claude for intelligent customization.

This module provides:
- ResumeTailoringService: Main orchestration for resume customization
- TailoredContent: Structured tailoring result
- Helper functions for formatting resume data
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

from src.core.database import Database, Job
from src.core.llm import ClaudeClient, TailoredResume
from src.core.pdf_generator import PDFGenerator
from src.utils.config import ConfigLoader, Resume, Achievements
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TailorResult:
    """Result of resume tailoring operation.
    
    Attributes:
        job_id: ID of job tailored for
        resume_id: Database ID of saved resume
        pdf_path: Path to generated PDF file
        summary: Tailored professional summary
        selected_achievements: Chosen achievements with tailored bullets
        highlighted_skills: Skills highlighted for this job
        tailoring_notes: Explanation of customizations
        cost_usd: Cost of Claude API call
    """
    job_id: int
    resume_id: int
    pdf_path: str
    summary: str
    selected_achievements: List[Dict]
    highlighted_skills: List[str]
    tailoring_notes: str
    cost_usd: float


class ResumeTailoringService:
    """Service for tailoring resumes to specific jobs using Claude.
    
    Workflow:
    1. Load job from database
    2. Load base resume and achievements from config
    3. Call Claude to generate tailored content
    4. Render HTML template
    5. Generate PDF
    6. Save to database
    7. Return result with details
    """

    def __init__(
        self,
        db: Optional[Database] = None,
        claude_client: Optional[ClaudeClient] = None,
        pdf_generator: Optional[PDFGenerator] = None,
        config: Optional[ConfigLoader] = None,
        output_dir: str = "data/resumes"
    ):
        """Initialize tailoring service.
        
        Args:
            db: Database instance (defaults to new Database())
            claude_client: Claude client (defaults to new ClaudeClient())
            pdf_generator: PDF generator (defaults to new PDFGenerator())
            config: Config loader (defaults to new ConfigLoader())
            output_dir: Directory to save PDF resumes
        """
        self.db = db or Database()
        self.claude = claude_client or ClaudeClient()
        self.pdf = pdf_generator or PDFGenerator()
        self.config = config or ConfigLoader()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("ResumeTailoringService initialized")

    async def tailor_resume_for_job(
        self,
        job_id: int,
        template: str = "modern"
    ) -> TailorResult:
        """Tailor resume for a specific job.
        
        Args:
            job_id: Database ID of job to tailor for
            template: Template to use ('modern' or 'ats_friendly')
            
        Returns:
            TailorResult with tailored content, PDF path, and database ID
            
        Raises:
            ValueError: If job not found
            Exception: If tailoring fails
        """
        # Load job from database
        job = self.db.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in database")
        
        # Load user data
        resume = self.config.get_resume()
        achievements = self.config.get_achievements()
        
        logger.info(f"Tailoring resume for: {job.title} @ {job.company}")
        
        # Format data for Claude
        resume_md = self._format_resume_markdown(resume)
        achievements_md = self._format_achievements_markdown(achievements)
        
        # Call Claude to generate tailored content
        try:
            tailored = await self.claude.tailor_resume(
                resume_markdown=resume_md,
                achievements_markdown=achievements_md,
                job_title=job.title,
                job_company=job.company,
                job_jd=job.jd_markdown or "",
                key_requirements=job.key_requirements or []
            )
        except Exception as e:
            logger.error(f"Claude tailor_resume failed for job {job_id}: {e}")
            raise
        
        # Build resume data for template
        resume_data = self._build_resume_data(resume, tailored, job)
        
        # Generate PDF
        pdf_filename = f"resume_job_{job_id}_{job.company.replace(' ', '_').replace('/', '_')}.pdf"
        pdf_path = self.output_dir / pdf_filename
        
        try:
            self.pdf.generate_resume_pdf(
                resume_data=resume_data,
                output_path=str(pdf_path),
                template=template
            )
            logger.info(f"PDF generated: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            # Continue anyway, save with empty pdf_path
            pdf_path = Path("")
        
        # Save to database
        resume_id = self.db.insert_resume(
            job_id=job_id,
            pdf_path=str(pdf_path),
            highlights=[a.get("name", "") for a in tailored.selected_achievements],
            tailoring_notes=tailored.tailoring_notes
        )
        
        logger.info(
            f"Resume tailored successfully for job {job_id}. "
            f"Cost: ${tailored.cost_usd:.4f}, Resume ID: {resume_id}, PDF: {pdf_path}"
        )
        
        return TailorResult(
            job_id=job_id,
            resume_id=resume_id,
            pdf_path=str(pdf_path),
            summary=tailored.summary,
            selected_achievements=tailored.selected_achievements,
            highlighted_skills=tailored.highlighted_skills,
            tailoring_notes=tailored.tailoring_notes,
            cost_usd=tailored.cost_usd
        )

    def _build_resume_data(
        self,
        resume: Resume,
        tailored: TailoredResume,
        job: Job
    ) -> Dict:
        """Build resume data dict for template rendering.

        Args:
            resume: Base resume
            tailored: Tailored content from Claude
            job: Target job

        Returns:
            Dict with all template variables
        """
        # Build skills list for template (category: items format)
        skills_list = []
        for category, items in resume.skills.items():
            if isinstance(items, list):
                skills_list.append({
                    "category": category,
                    "items": ", ".join(items)
                })
            else:
                skills_list.append({
                    "category": category,
                    "items": items
                })

        return {
            "personal_info": {
                "name": resume.personal_info.name,
                "title": resume.personal_info.title or "",
                "email": resume.personal_info.email,
                "phone": resume.personal_info.phone or "",
                "linkedin": resume.personal_info.linkedin or "",
                "github": resume.personal_info.github or "",
                "location": resume.personal_info.location or "",
            },
            "summary": tailored.summary if tailored.summary else "",
            "summary_bullets": resume.summary_bullets if resume.summary_bullets else [],
            "education": [
                {
                    "degree": edu.degree,
                    "institution": edu.institution,
                    "period": edu.period,
                    "gpa": edu.gpa or "",
                    "focus": edu.focus or "",
                    "details": edu.details or "",
                }
                for edu in resume.education
            ] if resume.education else [],
            "experience": tailored.selected_achievements,
            "projects": [
                {
                    "name": proj.name,
                    "period": proj.period,
                    "bullets": proj.description,
                }
                for proj in resume.projects
            ] if resume.projects else [],
            "skills": skills_list if skills_list else tailored.highlighted_skills,
            "target_job": {
                "title": job.title,
                "company": job.company,
            }
        }

    def _format_resume_markdown(self, resume: Resume) -> str:
        """Format Resume dataclass as markdown for Claude.

        Args:
            resume: Resume dataclass from config

        Returns:
            Markdown-formatted resume
        """
        lines = []

        # Personal info
        lines.append(f"# {resume.personal_info.name}")
        if resume.personal_info.title:
            lines.append(f"**Title:** {resume.personal_info.title}")
        lines.append(f"**Email:** {resume.personal_info.email}")
        if resume.personal_info.phone:
            lines.append(f"**Phone:** {resume.personal_info.phone}")
        if resume.personal_info.linkedin:
            lines.append(f"**LinkedIn:** {resume.personal_info.linkedin}")
        if resume.personal_info.github:
            lines.append(f"**GitHub:** {resume.personal_info.github}")
        if resume.personal_info.location:
            lines.append(f"**Location:** {resume.personal_info.location}")
        lines.append("")

        # Summary (bullet points or text)
        if resume.summary_bullets:
            lines.append("## Professional Summary")
            for bullet in resume.summary_bullets:
                lines.append(f"- {bullet}")
            lines.append("")
        elif resume.summary:
            lines.append("## Professional Summary")
            lines.append(resume.summary)
            lines.append("")

        # Education
        if resume.education:
            lines.append("## Education")
            for edu in resume.education:
                lines.append(f"### {edu.degree} - {edu.institution}")
                lines.append(f"*{edu.period}*")
                if edu.gpa:
                    lines.append(f"GPA: {edu.gpa}")
                if edu.focus:
                    lines.append(f"Focus: {edu.focus}")
                if edu.coursework:
                    lines.append(f"Coursework: {', '.join(edu.coursework)}")
                lines.append("")

        # Work experience
        if resume.work_experience:
            lines.append("## Work Experience")
            for exp in resume.work_experience:
                lines.append(f"### {exp.title} - {exp.company}")
                lines.append(f"*{exp.period}*")
                if exp.location:
                    lines.append(f"Location: {exp.location}")
                if exp.responsibilities:
                    for bullet in exp.responsibilities:
                        lines.append(f"- {bullet}")
                lines.append("")

        # Projects
        if resume.projects:
            lines.append("## Projects")
            for proj in resume.projects:
                lines.append(f"### {proj.name}")
                lines.append(f"*{proj.period}*")
                if proj.description:
                    for bullet in proj.description:
                        lines.append(f"- {bullet}")
                lines.append("")

        # Skills
        if resume.skills:
            lines.append("## Skills")
            if isinstance(resume.skills, dict):
                for category, skills in resume.skills.items():
                    lines.append(f"**{category}:** {', '.join(skills)}")
            else:
                lines.append(", ".join(resume.skills))
            lines.append("")
        
        return "\n".join(lines)

    def _format_achievements_markdown(self, achievements: Achievements) -> str:
        """Format Achievements dataclass as markdown for Claude.
        
        Args:
            achievements: Achievements dataclass from config
            
        Returns:
            Markdown-formatted achievements pool
        """
        lines = []
        lines.append("# Achievement Pool")
        lines.append("")
        
        for achievement in achievements.items:
            lines.append(f"## {achievement.name}")
            if achievement.company:
                lines.append(f"**Company:** {achievement.company}")
            if achievement.period:
                lines.append(f"**Period:** {achievement.period}")
            if achievement.category:
                lines.append(f"**Category:** {achievement.category}")
            if achievement.keywords:
                lines.append(f"**Keywords:** {', '.join(achievement.keywords)}")
            if achievement.bullets:
                lines.append("**Highlights:**")
                for bullet in achievement.bullets:
                    lines.append(f"- {bullet}")
            lines.append("")
        
        return "\n".join(lines)

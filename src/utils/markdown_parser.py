"""Markdown parser for configuration files."""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional


# Resume-related dataclasses
@dataclass
class PersonalInfo:
    """Personal information from resume."""
    name: str
    email: str
    phone: str = ""
    title: str = ""  # Job title/role
    linkedin: Optional[str] = None
    github: Optional[str] = None
    location: str = ""
    visa_status: str = ""


@dataclass
class Education:
    """Education entry from resume."""
    institution: str
    degree: str
    period: str
    gpa: Optional[str] = None
    coursework: List[str] = None
    focus: Optional[str] = None  # Area of focus
    details: Optional[str] = None  # Additional details

    def __post_init__(self):
        if self.coursework is None:
            self.coursework = []


@dataclass
class WorkExperience:
    """Work experience entry from resume."""
    title: str
    company: str
    period: str
    location: str
    responsibilities: List[str]
    technologies: List[str]


@dataclass
class Project:
    """Project entry from resume."""
    name: str
    period: str
    category: List[str]
    description: List[str]  # Bullet points
    technologies: List[str]


@dataclass
class Resume:
    """Complete resume data."""
    personal_info: PersonalInfo
    summary: str
    summary_bullets: List[str]  # Summary as bullet points
    education: List[Education]
    work_experience: List[WorkExperience]
    projects: List[Project]  # Projects section
    skills: Dict[str, List[str]]  # Category -> skills


# Preferences-related dataclasses
@dataclass
class LocationPreferences:
    """Location preferences for job search."""
    preferred: List[str]
    acceptable: List[str]
    not_acceptable: List[str]


@dataclass
class SalaryExpectations:
    """Salary expectations."""
    minimum: int
    target_min: int
    target_max: int
    currency: str


@dataclass
class KeywordFilters:
    """Keyword filters for job matching."""
    reject_keywords: List[str]    # Auto-reject if found
    prefer_keywords: List[str]    # Bonus points


@dataclass
class ApplicationSettings:
    """Application automation settings."""
    auto_apply_threshold: float   # Score >= this -> auto apply
    notify_threshold: float       # Score >= this -> notify user
    max_applications_per_day: int
    max_applications_per_hour: int
    scrape_interval_hours: int


@dataclass
class Preferences:
    """Complete preferences data."""
    target_positions: List[str]
    location: LocationPreferences
    visa_sponsorship_required: bool
    salary: SalaryExpectations
    blacklisted_companies: List[str]
    preferred_company_types: List[str]
    keywords: KeywordFilters
    settings: ApplicationSettings
    platforms: Dict[str, bool]    # Platform -> enabled


# Achievements-related dataclasses
@dataclass
class Achievement:
    """Single achievement/project."""
    name: str
    category: List[str]           # e.g., ["AI", "Backend"]
    keywords: List[str]           # For matching with JD
    bullets: List[str]            # Resume bullet points


@dataclass
class Achievements:
    """Collection of achievements."""
    items: List[Achievement]


# Credentials-related dataclasses
@dataclass
class PlatformCredential:
    """Credentials for a job platform."""
    platform: str
    email: str
    password: str


@dataclass
class APICredential:
    """Credentials for an API service."""
    service: str
    api_key: str
    api_url: Optional[str] = None
    extra: Dict[str, str] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


@dataclass
class Credentials:
    """All credentials for the job hunter."""
    platforms: Dict[str, PlatformCredential]  # platform_name -> credential
    apis: Dict[str, APICredential]            # service_name -> credential

    def get_platform(self, platform: str) -> Optional[PlatformCredential]:
        """Get credentials for a platform."""
        return self.platforms.get(platform.lower())

    def get_api(self, service: str) -> Optional[APICredential]:
        """Get credentials for an API service."""
        return self.apis.get(service.lower())


# LLM-related dataclasses
@dataclass
class LLMConfig:
    """Configuration for a specific LLM provider usage."""
    provider: str
    model: str
    purpose: str


@dataclass
class ProviderInfo:
    """Information about an available provider."""
    name: str
    env_var: str
    models: List[str]
    notes: str = ""


@dataclass
class LLMProviders:
    """LLM provider configuration."""
    active: Dict[str, LLMConfig]  # purpose -> config
    available: Dict[str, ProviderInfo]  # provider_name -> info

    def get_config(self, purpose: str) -> Optional[LLMConfig]:
        """Get config for a specific purpose."""
        return self.active.get(purpose.lower())


class MarkdownParser:
    """Parse structured markdown config files."""

    def parse_resume(self, content: str) -> Resume:
        """Parse resume.md into Resume dataclass."""
        sections = self._split_sections(content)

        # Parse summary - can be text or bullet points
        summary_section = sections.get("Summary", "")
        summary_bullets = self._parse_list_items(summary_section)
        summary_text = summary_section.strip() if not summary_bullets else ""

        return Resume(
            personal_info=self._parse_personal_info(sections.get("Personal Information", "")),
            summary=summary_text,
            summary_bullets=summary_bullets,
            education=self._parse_education(sections.get("Education", "")),
            work_experience=self._parse_work_experience(sections.get("Work Experience", "")),
            projects=self._parse_projects(sections.get("Projects", "")),
            skills=self._parse_skills(sections.get("Skills", ""))
        )

    def parse_preferences(self, content: str) -> Preferences:
        """Parse preferences.md into Preferences dataclass."""
        sections = self._split_sections(content)

        # Parse location preferences
        location_section = sections.get("Location Requirements", "")
        location_subsections = self._split_subsections(location_section)

        location = LocationPreferences(
            preferred=self._parse_list_items(location_subsections.get("Preferred", "")),
            acceptable=self._parse_list_items(location_subsections.get("Acceptable", "")),
            not_acceptable=self._parse_list_items(location_subsections.get("Not Acceptable", ""))
        )

        # Parse work authorization
        work_auth = self._parse_key_value_list(sections.get("Work Authorization", ""))
        visa_sponsorship_required = work_auth.get("Requires Visa Sponsorship", "No").lower() in ["yes", "true"]

        # Parse salary
        salary_data = self._parse_key_value_list(sections.get("Salary Expectations", ""))
        salary = self._parse_salary(salary_data)

        # Parse company preferences
        company_section = sections.get("Company Preferences", "")
        company_subsections = self._split_subsections(company_section)

        blacklisted_companies = self._parse_list_items(company_subsections.get("Blacklist (Do not apply)", ""))
        preferred_company_types = self._parse_list_items(company_subsections.get("Preferred Company Types", ""))

        # Parse keyword filters
        keyword_section = sections.get("Keyword Filters", "")
        keyword_subsections = self._split_subsections(keyword_section)

        keywords = KeywordFilters(
            reject_keywords=self._parse_list_items(keyword_subsections.get("Must NOT contain (auto-reject)", "")),
            prefer_keywords=self._parse_list_items(keyword_subsections.get("Preferred keywords (bonus points)", ""))
        )

        # Parse application settings
        settings_section = sections.get("Application Settings", "")
        settings_subsections = self._split_subsections(settings_section)

        thresholds = self._parse_key_value_list(settings_subsections.get("Decision Thresholds", ""))
        rate_limits = self._parse_key_value_list(settings_subsections.get("Rate Limits", ""))
        platforms_section = self._parse_key_value_list(settings_subsections.get("Platforms", ""))

        settings = ApplicationSettings(
            auto_apply_threshold=self._parse_float(thresholds.get("auto_apply_threshold", "0.85")),
            notify_threshold=self._parse_float(thresholds.get("notify_threshold", "0.60")),
            max_applications_per_day=self._parse_int(rate_limits.get("max_applications_per_day", "20")),
            max_applications_per_hour=self._parse_int(rate_limits.get("max_applications_per_hour", "5")),
            scrape_interval_hours=self._parse_int(rate_limits.get("scrape_interval_hours", "4"))
        )

        # Parse platforms
        platforms = {}
        for key, value in platforms_section.items():
            platforms[key] = value.lower() in ["enabled", "true", "yes"]

        return Preferences(
            target_positions=self._parse_list_items(sections.get("Target Positions", "")),
            location=location,
            visa_sponsorship_required=visa_sponsorship_required,
            salary=salary,
            blacklisted_companies=blacklisted_companies,
            preferred_company_types=preferred_company_types,
            keywords=keywords,
            settings=settings,
            platforms=platforms
        )

    def parse_achievements(self, content: str) -> Achievements:
        """Parse achievements.md into Achievements dataclass."""
        # Split by ## section headers (category sections)
        category_sections = self._split_sections(content)

        achievements = []

        for category_name, category_content in category_sections.items():
            # Skip non-achievement sections
            if category_name.lower().startswith("tips") or not category_content.strip():
                continue

            # Split by ### (individual achievements)
            achievement_sections = self._split_subsections(category_content)

            for achievement_name, achievement_content in achievement_sections.items():
                if not achievement_content.strip():
                    continue

                # Parse achievement fields
                parsed = self._parse_achievement_fields(achievement_content)

                achievements.append(Achievement(
                    name=achievement_name,
                    category=parsed.get("category", []),
                    keywords=parsed.get("keywords", []),
                    bullets=parsed.get("bullets", [])
                ))

        return Achievements(items=achievements)

    # Helper methods

    def _split_sections(self, content: str) -> Dict[str, str]:
        """Split markdown by ## headers."""
        sections = {}
        current_header = None
        current_content = []

        for line in content.split("\n"):
            # Skip single # headers (document title)
            if line.startswith("# ") and not line.startswith("## "):
                continue
            elif line.startswith("## ") and not line.startswith("### "):
                # Save previous section
                if current_header:
                    sections[current_header] = "\n".join(current_content)
                current_header = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_header:
            sections[current_header] = "\n".join(current_content)

        return sections

    def _split_subsections(self, content: str) -> Dict[str, str]:
        """Split content by ### headers."""
        return self._split_by_header(content, "### ")

    def _split_subsubsections(self, content: str) -> Dict[str, str]:
        """Split content by #### headers."""
        return self._split_by_header(content, "#### ")

    def _split_by_header(self, content: str, prefix: str) -> Dict[str, str]:
        """Split content by specified header prefix."""
        sections = {}
        current_header = None
        current_content = []
        prefix_len = len(prefix)

        for line in content.split("\n"):
            if line.startswith(prefix) and not line.startswith(prefix + "#"):
                # Save previous section
                if current_header:
                    sections[current_header] = "\n".join(current_content)
                current_header = line[prefix_len:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_header:
            sections[current_header] = "\n".join(current_content)

        return sections

    def _parse_list_items(self, content: str) -> List[str]:
        """Extract bullet points from content."""
        items = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ") and not line.startswith("- ["):
                # Skip example/placeholder items
                item = line[2:].strip()
                # Remove inline comments (after #)
                if " #" in item:
                    item = item.split(" #")[0].strip()
                if item and not item.startswith("["):
                    items.append(item)
        return items

    def _parse_key_value_list(self, content: str) -> Dict[str, str]:
        """Parse '- Key: Value' format."""
        result = {}
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ": " in line:
                line = line[2:]  # Remove "- "
                # Remove inline comments
                if " #" in line:
                    line = line.split(" #")[0].strip()
                key, value = line.split(": ", 1)
                result[key.strip()] = value.strip()
        return result

    def _parse_personal_info(self, content: str) -> PersonalInfo:
        """Parse personal info section."""
        data = self._parse_key_value_list(content)
        return PersonalInfo(
            name=data.get("Name", ""),
            email=data.get("Email", ""),
            phone=data.get("Phone", ""),
            title=data.get("Title", ""),
            linkedin=data.get("LinkedIn"),
            github=data.get("GitHub"),
            location=data.get("Location", ""),
            visa_status=data.get("Visa Status", "")
        )

    def _parse_education(self, content: str) -> List[Education]:
        """Parse education section."""
        # Split by ### (institution headers) - entries are ### Institution Name
        institution_sections = self._split_subsections(content)

        # Parse each institution
        education_list = []
        for institution, content in institution_sections.items():
            data = self._parse_key_value_list(content)

            # Parse coursework if present
            coursework = []
            coursework_str = data.get("Relevant Coursework", "")
            if coursework_str:
                coursework = [c.strip() for c in coursework_str.split(",")]

            education_list.append(Education(
                institution=institution,
                degree=data.get("Degree", ""),
                period=data.get("Period", ""),
                gpa=data.get("GPA"),
                coursework=coursework,
                focus=data.get("Focus"),
                details=data.get("Details")
            ))

        return education_list

    def _parse_work_experience(self, content: str) -> List[WorkExperience]:
        """Parse work experience section."""
        # Split by ### (job headers) - entries are ### Job @ Company
        job_sections = self._split_subsections(content)

        # Parse each job
        work_experience_list = []
        for job_header, job_content in job_sections.items():
            # Parse job header: "Title @ Company"
            if " @ " in job_header:
                title, company = job_header.split(" @ ", 1)
            else:
                title = job_header
                company = ""

            # Parse subsections (#### Responsibilities, #### Technologies)
            subsections = self._split_subsubsections(job_content)

            # Parse basic fields
            basic_fields = self._parse_key_value_list(job_content)

            # Parse responsibilities and technologies
            responsibilities = self._parse_list_items(subsections.get("Responsibilities", ""))

            # Technologies might be in a list or comma-separated
            tech_section = subsections.get("Technologies", "").strip()
            if tech_section.startswith("- "):
                technologies = self._parse_list_items(tech_section)
            else:
                # Comma-separated
                technologies = [t.strip() for t in tech_section.split(",") if t.strip()]

            work_experience_list.append(WorkExperience(
                title=title.strip(),
                company=company.strip(),
                period=basic_fields.get("Period", ""),
                location=basic_fields.get("Location", ""),
                responsibilities=responsibilities,
                technologies=technologies
            ))

        return work_experience_list

    def _parse_projects(self, content: str) -> List[Project]:
        """Parse projects section."""
        # Split by ### (project headers) - entries are ### Project Name
        project_sections = self._split_subsections(content)

        # Parse each project
        projects = []
        for project_name, project_content in project_sections.items():
            # Parse subsections (#### Description, #### Technologies)
            subsections = self._split_subsubsections(project_content)

            # Parse basic fields
            basic_fields = self._parse_key_value_list(project_content)

            # Parse description bullets
            description = self._parse_list_items(subsections.get("Description", ""))

            # Parse category
            category_str = basic_fields.get("Category", "")
            category = [c.strip() for c in category_str.split(",") if c.strip()]

            # Technologies
            tech_section = subsections.get("Technologies", "").strip()
            if tech_section.startswith("- "):
                technologies = self._parse_list_items(tech_section)
            else:
                technologies = [t.strip() for t in tech_section.split(",") if t.strip()]

            projects.append(Project(
                name=project_name,
                period=basic_fields.get("Period", ""),
                category=category,
                description=description,
                technologies=technologies
            ))

        return projects

    def _parse_skills(self, content: str) -> Dict[str, List[str]]:
        """Parse skills section."""
        # Split by ### (skill category headers) - entries are ### Category Name
        skill_sections = self._split_subsections(content)

        # Parse each category
        skills = {}
        for category, content in skill_sections.items():
            content = content.strip()
            if not content:
                continue

            # Skills can be list items or comma-separated
            if content.startswith("- "):
                skills[category] = self._parse_list_items(content)
            else:
                # Comma-separated
                skills[category] = [s.strip() for s in content.split(",") if s.strip()]

        return skills

    def _parse_salary(self, data: Dict[str, str]) -> SalaryExpectations:
        """Parse salary expectations."""
        minimum = self._parse_salary_amount(data.get("Minimum", "0"))

        target_str = data.get("Target", "0 - 0")
        if " - " in target_str:
            target_min_str, target_max_str = target_str.split(" - ", 1)
            target_min = self._parse_salary_amount(target_min_str)
            target_max = self._parse_salary_amount(target_max_str)
        else:
            target_min = minimum
            target_max = minimum

        currency = data.get("Currency", "USD")
        # Extract just the currency code
        currency = currency.split()[0].upper()

        return SalaryExpectations(
            minimum=minimum,
            target_min=target_min,
            target_max=target_max,
            currency=currency
        )

    def _parse_salary_amount(self, amount_str: str) -> int:
        """Parse salary amount from string like '$120,000 USD/year'."""
        # Remove currency symbols, commas, and text
        amount_str = re.sub(r'[^\d]', '', amount_str)
        return int(amount_str) if amount_str else 0

    def _parse_achievement_fields(self, content: str) -> Dict[str, any]:
        """Parse achievement fields (category, keywords, bullets)."""
        result = {
            "category": [],
            "keywords": [],
            "bullets": []
        }

        in_bullets = False
        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("- Category:"):
                category_str = line.split(":", 1)[1].strip()
                result["category"] = [c.strip() for c in category_str.split(",")]
            elif line.startswith("- Keywords:"):
                keywords_str = line.split(":", 1)[1].strip()
                result["keywords"] = [k.strip() for k in keywords_str.split(",")]
            elif line.startswith("- Bullets:"):
                in_bullets = True
            elif in_bullets and line.startswith("- "):
                result["bullets"].append(line[2:].strip())
            elif in_bullets and line.startswith("  - "):
                result["bullets"].append(line[4:].strip())

        return result

    def _parse_float(self, value: str) -> float:
        """Parse float from string, with default."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_int(self, value: str) -> int:
        """Parse int from string, with default."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    def parse_credentials(self, content: str) -> Credentials:
        """Parse credentials.md into Credentials dataclass.

        The file contains YAML-like blocks in code fences:
        ```yaml
        platform: linkedin
        email: user@example.com
        password: secret
        ```
        """
        platforms = {}
        apis = {}

        # Find all yaml code blocks
        yaml_pattern = r'```yaml\s*(.*?)```'
        blocks = re.findall(yaml_pattern, content, re.DOTALL)

        for block in blocks:
            data = self._parse_yaml_block(block)

            if 'platform' in data:
                # Platform credential
                platform = data['platform'].lower()
                platforms[platform] = PlatformCredential(
                    platform=platform,
                    email=data.get('email', ''),
                    password=data.get('password', '')
                )
            elif 'service' in data:
                # API credential
                service = data['service'].lower()
                extra = {k: v for k, v in data.items()
                        if k not in ['service', 'api_key', 'api_url']}
                apis[service] = APICredential(
                    service=service,
                    api_key=data.get('api_key', ''),
                    api_url=data.get('api_url'),
                    extra=extra if extra else None
                )

        return Credentials(platforms=platforms, apis=apis)

    def _parse_yaml_block(self, block: str) -> Dict[str, str]:
        """Parse a simple YAML-like block into a dictionary."""
        result = {}
        for line in block.strip().split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        return result

    def parse_llm_providers(self, content: str) -> LLMProviders:
        """Parse llm_providers.md into LLMProviders dataclass."""
        sections = self._split_sections(content)

        # Parse Active Providers
        active = {}
        active_section = sections.get("Active Providers", "")
        active_subsections = self._split_subsections(active_section)

        for purpose_name, config_text in active_subsections.items():
            data = self._parse_key_value_list(config_text)
            
            # Map section name to purpose key (e.g., "Filtering Provider" -> "filter")
            purpose_key = "filter" if "filtering" in purpose_name.lower() else "tailor"
            if "resume" in purpose_name.lower():
                purpose_key = "tailor"
                
            active[purpose_key] = LLMConfig(
                provider=data.get("Provider", "").lower(),
                model=data.get("Model", ""),
                purpose=data.get("Purpose", "")
            )

        # Parse Available Providers
        available = {}
        avail_section = sections.get("Available Providers", "")
        avail_subsections = self._split_subsections(avail_section)

        for provider_name, info_text in avail_subsections.items():
            data = self._parse_key_value_list(info_text)
            
            # Parse models list
            models_str = data.get("Models", "")
            models = [m.strip() for m in models_str.split(",")] if models_str else []

            # Clean provider name (remove parens like "GLM (智谱AI)")
            clean_name = provider_name.split("(")[0].strip().lower()

            available[clean_name] = ProviderInfo(
                name=clean_name,
                env_var=data.get("API Key Env", ""),
                models=models,
                notes=data.get("Notes", "")
            )

        return LLMProviders(active=active, available=available)

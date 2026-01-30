"""Unit tests for configuration parsing."""

import pytest
from src.utils.markdown_parser import (
    MarkdownParser,
    PersonalInfo,
    Education,
    WorkExperience,
    Resume,
    LocationPreferences,
    SalaryExpectations,
    KeywordFilters,
    ApplicationSettings,
    Preferences,
    Achievement,
    Achievements,
)
from src.utils.config import ConfigLoader, ConfigError, ConfigNotFoundError, ConfigParseError


class TestMarkdownParser:
    """Test MarkdownParser functionality."""

    def test_parse_personal_info(self):
        """Test parsing personal information."""
        parser = MarkdownParser()
        content = """
# Personal Information

- Name: John Doe
- Email: john@example.com
- Phone: +1-555-123-4567
- LinkedIn: linkedin.com/in/johndoe
- GitHub: github.com/johndoe
- Location: Vancouver, Canada
- Visa Status: Requires sponsorship
"""
        resume = parser.parse_resume(content)
        assert resume.personal_info.name == "John Doe"
        assert resume.personal_info.email == "john@example.com"
        assert resume.personal_info.phone == "+1-555-123-4567"
        assert resume.personal_info.linkedin == "linkedin.com/in/johndoe"
        assert resume.personal_info.github == "github.com/johndoe"
        assert resume.personal_info.location == "Vancouver, Canada"
        assert resume.personal_info.visa_status == "Requires sponsorship"

    def test_parse_summary(self):
        """Test parsing summary section."""
        parser = MarkdownParser()
        content = """
# Summary

Senior Software Engineer with 5+ years of experience in AI/ML systems.
Specialized in building scalable distributed systems.
"""
        resume = parser.parse_resume(content)
        assert "Senior Software Engineer" in resume.summary
        assert "5+ years" in resume.summary

    def test_parse_education(self):
        """Test parsing education section."""
        parser = MarkdownParser()
        content = """
# Education

## University of Example
- Degree: Master of Computer Science
- Period: 2018 - 2020
- GPA: 3.8/4.0
- Relevant Coursework: Machine Learning, Distributed Systems

## Another University
- Degree: Bachelor of Science
- Period: 2014 - 2018
"""
        resume = parser.parse_resume(content)
        assert len(resume.education) == 2

        edu1 = resume.education[0]
        assert edu1.institution == "University of Example"
        assert edu1.degree == "Master of Computer Science"
        assert edu1.period == "2018 - 2020"
        assert edu1.gpa == "3.8/4.0"
        assert "Machine Learning" in edu1.coursework
        assert "Distributed Systems" in edu1.coursework

        edu2 = resume.education[1]
        assert edu2.institution == "Another University"
        assert edu2.degree == "Bachelor of Science"

    def test_parse_work_experience(self):
        """Test parsing work experience section."""
        parser = MarkdownParser()
        content = """
# Work Experience

## Senior Software Engineer @ Company A
- Period: 2022.06 - Present
- Location: Remote

### Responsibilities
- Led development of enterprise AI platform
- Implemented RAG pipeline

### Technologies
Python, PyTorch, FastAPI, PostgreSQL

## Software Engineer @ Company B
- Period: 2019.01 - 2022.05
- Location: Vancouver, Canada

### Responsibilities
- Built high-throughput messaging system

### Technologies
Java, Kafka, Kubernetes
"""
        resume = parser.parse_resume(content)
        assert len(resume.work_experience) == 2

        job1 = resume.work_experience[0]
        assert job1.title == "Senior Software Engineer"
        assert job1.company == "Company A"
        assert job1.period == "2022.06 - Present"
        assert job1.location == "Remote"
        assert "Led development of enterprise AI platform" in job1.responsibilities
        assert "Implemented RAG pipeline" in job1.responsibilities
        assert "Python" in job1.technologies
        assert "PostgreSQL" in job1.technologies

        job2 = resume.work_experience[1]
        assert job2.title == "Software Engineer"
        assert job2.company == "Company B"
        assert "Java" in job2.technologies

    def test_parse_skills(self):
        """Test parsing skills section."""
        parser = MarkdownParser()
        content = """
# Skills

## Programming Languages
Python, Java, TypeScript, Go, SQL

## AI/ML
PyTorch, TensorFlow, LangChain, RAG

## Backend
FastAPI, Spring Boot, PostgreSQL, Redis
"""
        resume = parser.parse_resume(content)
        assert "Programming Languages" in resume.skills
        assert "Python" in resume.skills["Programming Languages"]
        assert "Java" in resume.skills["Programming Languages"]

        assert "AI/ML" in resume.skills
        assert "PyTorch" in resume.skills["AI/ML"]
        assert "RAG" in resume.skills["AI/ML"]

    def test_parse_preferences_target_positions(self):
        """Test parsing target positions."""
        parser = MarkdownParser()
        content = """
## Target Positions

- AI Engineer
- ML Engineer
- Backend Engineer
"""
        prefs = parser.parse_preferences(content)
        assert len(prefs.target_positions) == 3
        assert "AI Engineer" in prefs.target_positions
        assert "ML Engineer" in prefs.target_positions

    def test_parse_location_preferences(self):
        """Test parsing location preferences."""
        parser = MarkdownParser()
        content = """
## Location Requirements

### Preferred
- Remote (fully remote)
- United States (remote)

### Acceptable
- Hybrid (max 2 days/week in office)

### Not Acceptable
- Onsite only
- Relocation required
"""
        prefs = parser.parse_preferences(content)
        assert len(prefs.location.preferred) == 2
        assert "Remote (fully remote)" in prefs.location.preferred
        assert len(prefs.location.acceptable) == 1
        assert "Hybrid (max 2 days/week in office)" in prefs.location.acceptable
        assert len(prefs.location.not_acceptable) == 2

    def test_parse_salary_expectations(self):
        """Test parsing salary expectations."""
        parser = MarkdownParser()
        content = """
## Salary Expectations

- Minimum: $120,000 USD/year
- Target: $150,000 - $200,000 USD/year
- Currency: USD preferred, CAD acceptable
"""
        prefs = parser.parse_preferences(content)
        assert prefs.salary.minimum == 120000
        assert prefs.salary.target_min == 150000
        assert prefs.salary.target_max == 200000
        assert prefs.salary.currency == "USD"

    def test_parse_blacklisted_companies(self):
        """Test parsing blacklisted companies."""
        parser = MarkdownParser()
        content = """
## Company Preferences

### Blacklist (Do not apply)
- Revature
- Infosys
- Any staffing/consulting agency

### Preferred Company Types
- Product companies
- AI-focused startups (Series A+)
"""
        prefs = parser.parse_preferences(content)
        assert len(prefs.blacklisted_companies) == 3
        assert "Revature" in prefs.blacklisted_companies
        assert len(prefs.preferred_company_types) == 2
        assert "Product companies" in prefs.preferred_company_types

    def test_parse_keyword_filters(self):
        """Test parsing keyword filters."""
        parser = MarkdownParser()
        content = """
## Keyword Filters

### Must NOT contain (auto-reject)
- clearance required
- security clearance
- US citizen only

### Preferred keywords (bonus points)
- visa sponsorship available
- remote friendly
- LLM
"""
        prefs = parser.parse_preferences(content)
        assert len(prefs.keywords.reject_keywords) == 3
        assert "clearance required" in prefs.keywords.reject_keywords
        assert len(prefs.keywords.prefer_keywords) == 3
        assert "visa sponsorship available" in prefs.keywords.prefer_keywords

    def test_parse_application_settings(self):
        """Test parsing application settings."""
        parser = MarkdownParser()
        content = """
## Application Settings

### Decision Thresholds
- auto_apply_threshold: 0.85
- notify_threshold: 0.60

### Rate Limits
- max_applications_per_day: 20
- max_applications_per_hour: 5
- scrape_interval_hours: 4

### Platforms
- linkedin: enabled
- indeed: enabled
- wellfound: disabled
"""
        prefs = parser.parse_preferences(content)
        assert prefs.settings.auto_apply_threshold == 0.85
        assert prefs.settings.notify_threshold == 0.60
        assert prefs.settings.max_applications_per_day == 20
        assert prefs.settings.max_applications_per_hour == 5
        assert prefs.settings.scrape_interval_hours == 4

        assert prefs.platforms["linkedin"] is True
        assert prefs.platforms["indeed"] is True
        assert prefs.platforms["wellfound"] is False

    def test_parse_achievements(self):
        """Test parsing achievements."""
        parser = MarkdownParser()
        content = """
# Career Achievements

## AI/ML Projects

### Newland AI Platform
- Category: AI, Backend, Leadership
- Keywords: AI, RAG, LLM, Python, FastAPI
- Bullets:
  - Led development of enterprise AI platform serving 10K+ daily active users
  - Implemented RAG pipeline with ChromaDB, reducing response latency by 40%
  - Designed multi-tenant architecture supporting 50+ enterprise clients

### Vibe Coding Assistant
- Category: AI, Developer Tools
- Keywords: LLM, Code Generation, Python
- Bullets:
  - Built AI-powered coding assistant with context-aware code completion
  - Achieved 85% acceptance rate for AI-generated suggestions

## Backend Projects

### Messaging System
- Category: Backend, High-Scale
- Keywords: Kafka, Java, Microservices
- Bullets:
  - Architected high-throughput messaging system processing 1M+ events/day
  - Achieved 99.9% uptime through redundancy
"""
        achievements = parser.parse_achievements(content)
        assert len(achievements.items) == 3

        ai_platform = achievements.items[0]
        assert ai_platform.name == "Newland AI Platform"
        assert "AI" in ai_platform.category
        assert "Backend" in ai_platform.category
        assert "RAG" in ai_platform.keywords
        assert "Python" in ai_platform.keywords
        assert len(ai_platform.bullets) == 3
        assert "10K+ daily active users" in ai_platform.bullets[0]

        messaging = achievements.items[2]
        assert messaging.name == "Messaging System"
        assert "Backend" in messaging.category
        assert "Kafka" in messaging.keywords


class TestAchievements:
    """Test Achievements dataclass methods."""

    def test_get_by_category(self):
        """Test filtering achievements by category."""
        achievements = Achievements(items=[
            Achievement(
                name="AI Platform",
                category=["AI", "Backend"],
                keywords=["RAG", "LLM"],
                bullets=["Built AI platform"]
            ),
            Achievement(
                name="Backend System",
                category=["Backend"],
                keywords=["Java", "Kafka"],
                bullets=["Built messaging system"]
            ),
            Achievement(
                name="Frontend App",
                category=["Frontend"],
                keywords=["React", "TypeScript"],
                bullets=["Built web app"]
            )
        ])

        ai_items = achievements.get_by_category("AI")
        assert len(ai_items) == 1
        assert ai_items[0].name == "AI Platform"

        backend_items = achievements.get_by_category("Backend")
        assert len(backend_items) == 2

    def test_get_by_keywords(self):
        """Test filtering achievements by keywords."""
        achievements = Achievements(items=[
            Achievement(
                name="AI Platform",
                category=["AI"],
                keywords=["RAG", "LLM", "Python"],
                bullets=["Built AI platform"]
            ),
            Achievement(
                name="Backend System",
                category=["Backend"],
                keywords=["Java", "Kafka"],
                bullets=["Built messaging system"]
            )
        ])

        matches = achievements.get_by_keywords(["RAG", "LLM"])
        assert len(matches) == 1
        assert matches[0].name == "AI Platform"

        matches = achievements.get_by_keywords(["Python"])
        assert len(matches) == 1

        matches = achievements.get_by_keywords(["Nonexistent"])
        assert len(matches) == 0

    def test_select_for_jd(self):
        """Test selecting most relevant achievements for JD."""
        achievements = Achievements(items=[
            Achievement(
                name="AI Platform",
                category=["AI"],
                keywords=["RAG", "LLM", "Python", "FastAPI"],
                bullets=["Built AI platform"]
            ),
            Achievement(
                name="Backend System",
                category=["Backend"],
                keywords=["Java", "Kafka"],
                bullets=["Built messaging system"]
            ),
            Achievement(
                name="Web App",
                category=["Frontend"],
                keywords=["React", "Python"],
                bullets=["Built web app"]
            )
        ])

        # JD keywords match AI Platform best (3 matches)
        jd_keywords = ["RAG", "LLM", "Python", "AWS"]
        selected = achievements.select_for_jd(jd_keywords, max_items=2)

        assert len(selected) <= 2
        assert selected[0].name == "AI Platform"  # Highest score (3 matches)

    def test_select_for_jd_case_insensitive(self):
        """Test keyword matching is case-insensitive."""
        achievements = Achievements(items=[
            Achievement(
                name="AI Platform",
                category=["AI"],
                keywords=["rag", "llm", "python"],
                bullets=["Built AI platform"]
            )
        ])

        jd_keywords = ["RAG", "LLM"]
        selected = achievements.select_for_jd(jd_keywords)

        assert len(selected) == 1
        assert selected[0].name == "AI Platform"


class TestConfigLoader:
    """Test ConfigLoader functionality."""

    def test_config_not_found(self, tmp_path):
        """Test error when config file doesn't exist."""
        loader = ConfigLoader(config_dir=str(tmp_path))

        with pytest.raises(ConfigNotFoundError):
            loader.get_resume()

        with pytest.raises(ConfigNotFoundError):
            loader.get_preferences()

        with pytest.raises(ConfigNotFoundError):
            loader.get_achievements()

    def test_validate_missing_files(self, tmp_path):
        """Test validation with missing files."""
        loader = ConfigLoader(config_dir=str(tmp_path))
        errors = loader.validate()

        assert len(errors) >= 3  # At least one error per file
        assert any("Resume" in err for err in errors)
        assert any("Preferences" in err for err in errors)
        assert any("Achievements" in err for err in errors)

    def test_validate_resume_fields(self, tmp_path):
        """Test resume validation rules."""
        # Create resume with missing name
        resume_path = tmp_path / "resume.md"
        resume_path.write_text("""
# Personal Information

- Name:
- Email: invalid-email
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        errors = loader.validate()

        assert any("Name is required" in err for err in errors)
        assert any("Invalid email format" in err for err in errors)

    def test_validate_preferences_thresholds(self, tmp_path):
        """Test preferences validation rules."""
        prefs_path = tmp_path / "preferences.md"
        prefs_path.write_text("""
## Target Positions

- AI Engineer

## Salary Expectations

- Minimum: $0 USD/year
- Target: $150,000 - $200,000 USD/year
- Currency: USD

## Application Settings

### Decision Thresholds
- auto_apply_threshold: 1.5
- notify_threshold: 0.95

### Rate Limits
- max_applications_per_day: -1
- max_applications_per_hour: 5
- scrape_interval_hours: 4
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        errors = loader.validate()

        assert any("Minimum salary must be positive" in err for err in errors)
        assert any("auto_apply_threshold must be between" in err for err in errors)
        assert any("notify_threshold must be <=" in err for err in errors)
        assert any("max_applications_per_day must be positive" in err for err in errors)

    def test_reload_clears_cache(self, tmp_path):
        """Test that reload clears the cache."""
        resume_path = tmp_path / "resume.md"
        resume_path.write_text("""
# Personal Information

- Name: John Doe
- Email: john@example.com
""")

        loader = ConfigLoader(config_dir=str(tmp_path))

        # Load first time
        resume1 = loader.get_resume()
        assert resume1.personal_info.name == "John Doe"

        # Modify file
        resume_path.write_text("""
# Personal Information

- Name: Jane Smith
- Email: jane@example.com
""")

        # Should still get cached version
        resume2 = loader.get_resume()
        assert resume2.personal_info.name == "John Doe"

        # After reload, should get new version
        loader.reload()
        resume3 = loader.get_resume()
        assert resume3.personal_info.name == "Jane Smith"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

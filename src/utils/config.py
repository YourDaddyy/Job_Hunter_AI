"""Configuration loader with caching and validation."""

from pathlib import Path
from functools import lru_cache
from typing import List

from .markdown_parser import (
    MarkdownParser,
    Resume,
    Preferences,
    Achievements,
    Credentials,
    LLMProviders,
    LLMConfig,
)


# Exception classes
class ConfigError(Exception):
    """Base configuration error."""
    pass


class ConfigNotFoundError(ConfigError):
    """Config file not found."""
    pass


class ConfigParseError(ConfigError):
    """Failed to parse config file."""
    pass


class ConfigValidationError(ConfigError):
    """Config validation failed."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Validation failed: {', '.join(errors)}")


class ConfigLoader:
    """Load and cache configuration files."""

    def __init__(self, config_dir: str = "config"):
        """Initialize config loader.

        Args:
            config_dir: Directory containing config files (default: "config")
        """
        self.config_dir = Path(config_dir)
        self.parser = MarkdownParser()

    @lru_cache(maxsize=1)
    def get_resume(self) -> Resume:
        """Load and parse resume.md.

        Returns:
            Resume dataclass instance

        Raises:
            ConfigNotFoundError: If resume.md doesn't exist
            ConfigParseError: If parsing fails
        """
        path = self.config_dir / "resume.md"
        if not path.exists():
            raise ConfigNotFoundError(f"Resume file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            return self.parser.parse_resume(content)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse resume: {e}") from e

    @lru_cache(maxsize=1)
    def get_preferences(self) -> Preferences:
        """Load and parse preferences.md.

        Returns:
            Preferences dataclass instance

        Raises:
            ConfigNotFoundError: If preferences.md doesn't exist
            ConfigParseError: If parsing fails
        """
        path = self.config_dir / "preferences.md"
        if not path.exists():
            raise ConfigNotFoundError(f"Preferences file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            return self.parser.parse_preferences(content)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse preferences: {e}") from e

    @lru_cache(maxsize=1)
    def get_achievements(self) -> Achievements:
        """Load and parse achievements.md.

        Returns:
            Achievements dataclass instance

        Raises:
            ConfigNotFoundError: If achievements.md doesn't exist
            ConfigParseError: If parsing fails
        """
        path = self.config_dir / "achievements.md"
        if not path.exists():
            raise ConfigNotFoundError(f"Achievements file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            return self.parser.parse_achievements(content)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse achievements: {e}") from e

    @lru_cache(maxsize=1)
    def get_credentials(self) -> Credentials:
        """Load and parse credentials.md.

        Returns:
            Credentials dataclass instance

        Raises:
            ConfigNotFoundError: If credentials.md doesn't exist
            ConfigParseError: If parsing fails
        """
        path = self.config_dir / "credentials.md"
        if not path.exists():
            raise ConfigNotFoundError(
                f"Credentials file not found: {path}. "
                "Copy config/credentials.example.md to config/credentials.md"
            )

        try:
            content = path.read_text(encoding="utf-8")
            return self.parser.parse_credentials(content)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse credentials: {e}") from e

    @lru_cache(maxsize=1)
    def get_llm_providers(self) -> LLMProviders:
        """Load and parse llm_providers.md.

        Returns:
            LLMProviders dataclass instance
        """
        path = self.config_dir / "llm_providers.md"
        # If file doesn't exist, return default (implemented in factory)
        if not path.exists():
             # Basic default fallback
             return LLMProviders(
                 active={
                     "filter": LLMConfig("glm", "glm-4-flash", "filter"),
                     "tailor": LLMConfig("glm", "glm-4-flash", "tailor")
                 },
                 available={}
             )

        try:
            content = path.read_text(encoding="utf-8")
            return self.parser.parse_llm_providers(content)
        except Exception as e:
            raise ConfigParseError(f"Failed to parse llm_providers: {e}") from e

    def reload(self):
        """Clear cache and reload all configs."""
        self.get_resume.cache_clear()
        self.get_preferences.cache_clear()
        self.get_achievements.cache_clear()
        self.get_credentials.cache_clear()
        self.get_llm_providers.cache_clear()

    def validate(self) -> List[str]:
        """Validate all config files.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check resume
        try:
            resume = self.get_resume()

            if not resume.personal_info.name:
                errors.append("Resume: Name is required")
            if not resume.personal_info.email:
                errors.append("Resume: Email is required")
            elif "@" not in resume.personal_info.email:
                errors.append("Resume: Invalid email format")

            if not resume.work_experience and not resume.education:
                errors.append("Resume: At least work experience or education is recommended")

        except ConfigNotFoundError as e:
            errors.append(str(e))
        except ConfigParseError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Resume: Unexpected error - {e}")

        # Check preferences
        try:
            prefs = self.get_preferences()

            if not prefs.target_positions:
                errors.append("Preferences: At least one target position required")

            if prefs.salary.minimum <= 0:
                errors.append("Preferences: Minimum salary must be positive")

            if not (0.0 <= prefs.settings.auto_apply_threshold <= 1.0):
                errors.append("Preferences: auto_apply_threshold must be between 0.0 and 1.0")

            if not (0.0 <= prefs.settings.notify_threshold <= 1.0):
                errors.append("Preferences: notify_threshold must be between 0.0 and 1.0")

            if prefs.settings.notify_threshold > prefs.settings.auto_apply_threshold:
                errors.append("Preferences: notify_threshold must be <= auto_apply_threshold")

            if prefs.settings.max_applications_per_day <= 0:
                errors.append("Preferences: max_applications_per_day must be positive")

            if prefs.settings.max_applications_per_hour <= 0:
                errors.append("Preferences: max_applications_per_hour must be positive")

            if prefs.settings.scrape_interval_hours <= 0:
                errors.append("Preferences: scrape_interval_hours must be positive")

        except ConfigNotFoundError as e:
            errors.append(str(e))
        except ConfigParseError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Preferences: Unexpected error - {e}")

        # Check achievements
        try:
            achievements = self.get_achievements()

            if not achievements.items:
                errors.append("Achievements: At least one achievement required")

            for i, achievement in enumerate(achievements.items):
                if not achievement.name:
                    errors.append(f"Achievements: Achievement #{i+1} missing name")
                if not achievement.bullets:
                    errors.append(f"Achievements: Achievement '{achievement.name}' has no bullets")

        except ConfigNotFoundError as e:
            errors.append(str(e))
        except ConfigParseError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Achievements: Unexpected error - {e}")

        return errors


# Global instance for convenience
config = ConfigLoader()

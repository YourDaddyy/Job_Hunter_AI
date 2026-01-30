"""
Antigravity Instruction Generator.

Reads job search preferences and platform credentials to generate
JSON instruction files for the Antigravity agent to scrape jobs.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from .platform_configs import (
    PLATFORM_INSTRUCTIONS,
    PLATFORM_PRIORITY,
    DATA_SCHEMA,
    get_platform_instruction
)


class InstructionGenerator:
    """Generates Antigravity scraping instructions from preferences and credentials."""

    def __init__(
        self,
        preferences_path: str = "W:\\Code\\job_viewer\\config\\preferences.md",
        credentials_path: str = "W:\\Code\\job_viewer\\config\\credentials.md",
    ):
        """
        Initialize the instruction generator.

        Args:
            preferences_path: Path to preferences.md file
            credentials_path: Path to credentials.md file
        """
        self.preferences_path = Path(preferences_path)
        self.credentials_path = Path(credentials_path)
        self.preferences = {}
        self.credentials = {}

    def read_preferences(self) -> Dict[str, Any]:
        """
        Parse preferences.md to extract job search preferences.

        Returns:
            Dictionary containing job titles, locations, filters, etc.
        """
        if not self.preferences_path.exists():
            raise FileNotFoundError(f"Preferences file not found: {self.preferences_path}")

        with open(self.preferences_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract job titles from Primary Interest section
        job_titles = []
        primary_match = re.search(
            r'### Primary Interest:.*?\n(.*?)(?=###|\n## )',
            content,
            re.DOTALL
        )
        if primary_match:
            lines = primary_match.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- '):
                    title = line[2:].strip()
                    if title and not title.startswith('Focus on') and not title.startswith('Strong background'):
                        job_titles.append(title)

        # Extract secondary job titles
        secondary_match = re.search(
            r'### Secondary Interest:.*?\n(.*?)(?=###|\n## )',
            content,
            re.DOTALL
        )
        if secondary_match:
            lines = secondary_match.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- '):
                    title = line[2:].strip()
                    if title and not title.startswith('Strong background'):
                        job_titles.append(title)

        # Extract also consider titles
        also_match = re.search(
            r'### Also Consider\n(.*?)(?=\n## )',
            content,
            re.DOTALL
        )
        if also_match:
            lines = also_match.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- '):
                    job_titles.append(line[2:].strip())

        # Extract location preferences
        locations = []
        location_match = re.search(
            r'### Preferred\n(.*?)(?=###)',
            content,
            re.DOTALL
        )
        if location_match:
            loc_section = location_match.group(1)
            lines = loc_section.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- '):
                    loc = line[2:].strip()
                    # Simplify location strings
                    if 'Remote' in loc or 'Canada' in loc:
                        locations.append(loc)

        # Extract salary requirements
        min_salary = None
        salary_match = re.search(r'- Minimum: \$?([\d,]+)', content)
        if salary_match:
            salary_str = salary_match.group(1).replace(',', '')
            min_salary = int(salary_str)

        # Check for remote only requirement
        remote_only = False
        if '- Remote (fully remote)' in content or '- Onsite only' in content:
            remote_only = True

        # Check for visa sponsorship
        visa_sponsorship_required = False
        if 'Requires Visa Sponsorship' in content:
            # Parse the specific requirements
            visa_match = re.search(r'Requires Visa Sponsorship: (.+)', content)
            if visa_match:
                visa_text = visa_match.group(1).lower()
                # "No (for Canada), Open to TN sponsorship (for US)"
                # This means visa NOT required for Canada, but open to TN for US
                visa_sponsorship_required = False

        # Extract enabled platforms
        enabled_platforms = []
        platform_section = re.search(r'### Platforms\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if platform_section:
            lines = platform_section.group(1).strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- ') and ': enabled' in line:
                    platform = line.split(':')[0].replace('- ', '').strip()
                    enabled_platforms.append(platform)

        self.preferences = {
            'job_titles': job_titles,
            'locations': locations if locations else ['Remote', 'Canada'],
            'filters': {
                'remote_only': remote_only,
                'visa_sponsorship_required': visa_sponsorship_required,
                'min_salary': min_salary,
            },
            'enabled_platforms': enabled_platforms if enabled_platforms else ['linkedin', 'indeed', 'wellfound'],
        }

        return self.preferences

    def read_credentials(self) -> Dict[str, Dict[str, str]]:
        """
        Parse credentials.md to extract platform login credentials.

        Returns:
            Dictionary mapping platform names to their credentials
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")

        with open(self.credentials_path, 'r', encoding='utf-8') as f:
            content = f.read()

        credentials = {}

        # Extract LinkedIn credentials
        linkedin_match = re.search(
            r'### LinkedIn.*?```yaml\n(.*?)\n```',
            content,
            re.DOTALL
        )
        if linkedin_match:
            creds = self._parse_yaml_block(linkedin_match.group(1))
            credentials['linkedin'] = {
                'email': creds.get('email', ''),
                'password': creds.get('password', ''),
            }

        # Extract Indeed credentials
        indeed_match = re.search(
            r'### Indeed.*?```yaml\n(.*?)\n```',
            content,
            re.DOTALL
        )
        if indeed_match:
            creds = self._parse_yaml_block(indeed_match.group(1))
            credentials['indeed'] = {
                'email': creds.get('email', ''),
                'password': creds.get('password', ''),
                'login_method': creds.get('login_method', 'email'),
            }

        # Extract Wellfound credentials
        wellfound_match = re.search(
            r'### Wellfound.*?```yaml\n(.*?)\n```',
            content,
            re.DOTALL
        )
        if wellfound_match:
            creds = self._parse_yaml_block(wellfound_match.group(1))
            credentials['wellfound'] = {
                'email': creds.get('email', ''),
                'password': creds.get('password', ''),
            }

        # Extract Glassdoor credentials
        glassdoor_match = re.search(
            r'### Glassdoor.*?```yaml\n(.*?)\n```',
            content,
            re.DOTALL
        )
        if glassdoor_match:
            creds = self._parse_yaml_block(glassdoor_match.group(1))
            credentials['glassdoor'] = {
                'email': creds.get('email', ''),
                'password': creds.get('password', ''),
            }

        self.credentials = credentials
        return credentials

    def _parse_yaml_block(self, yaml_text: str) -> Dict[str, str]:
        """
        Parse a simple YAML block into a dictionary.

        Args:
            yaml_text: YAML formatted text

        Returns:
            Dictionary of key-value pairs
        """
        result = {}
        for line in yaml_text.strip().split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        return result

    def generate_instructions(
        self,
        output_dir: str = "W:\\Code\\job_viewer\\instructions",
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete Antigravity instruction JSON file.

        Args:
            output_dir: Directory to save instruction file
            filename: Optional custom filename (defaults to timestamped name)

        Returns:
            Dictionary containing the generated instructions
        """
        # Read preferences and credentials
        if not self.preferences:
            self.read_preferences()
        if not self.credentials:
            self.read_credentials()

        # Generate timestamp
        timestamp = datetime.now().isoformat()

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename
        if filename is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            filename = f"scrape_jobs_{date_str}.json"

        # Build instructions dictionary
        instructions = {
            '_metadata': {
                'generated_at': timestamp,
                'task_type': 'scrape_jobs',
                'version': '1.0',
            },
            'credentials': self.credentials,
            'search_parameters': {
                'job_titles': self.preferences['job_titles'],
                'locations': self.preferences['locations'],
                'filters': self.preferences['filters'],
            },
            'platforms': [],
            'data_schema': DATA_SCHEMA,
        }

        # Generate platform-specific instructions
        data_dir = Path("W:\\Code\\job_viewer\\data")
        data_dir.mkdir(parents=True, exist_ok=True)

        for platform in self.preferences['enabled_platforms']:
            if platform not in self.credentials:
                print(f"Warning: No credentials found for {platform}, skipping...")
                continue

            # Get platform credentials
            platform_creds = self.credentials[platform]

            # Format job titles and locations as comma-separated strings
            job_titles_str = ', '.join(self.preferences['job_titles'][:5])  # Limit to first 5 for brevity
            locations_str = ', '.join(self.preferences['locations'])

            # Generate instruction text
            instruction_params = {
                'email': platform_creds.get('email', ''),
                'password': platform_creds.get('password', '***'),  # Mask in instructions
                'job_titles': job_titles_str,
                'locations': locations_str,
                'remote_only': self.preferences['filters']['remote_only'],
                'min_salary': self.preferences['filters']['min_salary'],
                'visa_sponsorship_required': self.preferences['filters']['visa_sponsorship_required'],
                'output_file': str(data_dir / f"{platform}_scraped.json"),
            }

            instruction_text = get_platform_instruction(platform, **instruction_params)

            platform_config = {
                'name': platform,
                'priority': PLATFORM_PRIORITY.get(platform, 'medium'),
                'instructions': instruction_text,
                'output_file': str(data_dir / f"{platform}_scraped.json"),
            }

            instructions['platforms'].append(platform_config)

        # Save to file
        output_file = output_path / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(instructions, f, indent=2, ensure_ascii=False)

        print(f"Generated instruction file: {output_file}")
        return {
            'instructions': instructions,
            'output_file': str(output_file),
        }

    def generate_sample(self, output_file: str = "W:\\Code\\job_viewer\\instructions\\scrape_jobs_example.json"):
        """
        Generate a sample instruction file for demonstration.

        Args:
            output_file: Path to save the sample file
        """
        return self.generate_instructions(
            output_dir=str(Path(output_file).parent),
            filename=Path(output_file).name
        )


def main():
    """CLI entry point for generating instructions."""
    generator = InstructionGenerator()

    print("Reading preferences from config/preferences.md...")
    preferences = generator.read_preferences()
    print(f"Found {len(preferences['job_titles'])} job titles")
    print(f"Locations: {', '.join(preferences['locations'])}")
    print(f"Enabled platforms: {', '.join(preferences['enabled_platforms'])}")

    print("\nReading credentials from config/credentials.md...")
    credentials = generator.read_credentials()
    print(f"Found credentials for: {', '.join(credentials.keys())}")

    print("\nGenerating Antigravity instructions...")
    result = generator.generate_instructions()

    print(f"\nSuccess! Generated instruction file:")
    print(f"  {result['output_file']}")
    print(f"\nTo run with Antigravity:")
    print(f"  antigravity run {result['output_file']}")


if __name__ == '__main__':
    main()

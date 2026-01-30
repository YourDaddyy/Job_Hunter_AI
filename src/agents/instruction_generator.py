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
        preferences_path: str = "config/preferences.md",
        credentials_path: str = "config/credentials.md",
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

        Supports new format with Primary/Secondary/Tertiary sections.

        Returns:
            Dictionary containing job titles, locations, filters, etc.
        """
        if not self.preferences_path.exists():
            raise FileNotFoundError(f"Preferences file not found: {self.preferences_path}")

        with open(self.preferences_path, 'r', encoding='utf-8') as f:
            content = f.read()

        job_titles = []

        # NEW FORMAT: ### Primary (X positions)
        primary_match = re.search(
            r'### Primary \(\d+ positions?\).*?\n(.*?)(?=###|\n## )',
            content,
            re.DOTALL
        )
        if primary_match:
            job_titles.extend(self._extract_titles_from_section(primary_match.group(1)))

        # NEW FORMAT: ### Secondary (X positions)
        secondary_match = re.search(
            r'### Secondary \(\d+ positions?\).*?\n(.*?)(?=###|\n## )',
            content,
            re.DOTALL
        )
        if secondary_match:
            job_titles.extend(self._extract_titles_from_section(secondary_match.group(1)))

        # NEW FORMAT: ### Tertiary (X positions)
        tertiary_match = re.search(
            r'### Tertiary \(\d+ positions?\).*?\n(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL
        )
        if tertiary_match:
            job_titles.extend(self._extract_titles_from_section(tertiary_match.group(1)))

        # FALLBACK: Old format support
        if not job_titles:
            # Extract job titles from Primary Interest section (old format)
            primary_match = re.search(
                r'### Primary Interest:.*?\n(.*?)(?=###|\n## )',
                content,
                re.DOTALL
            )
            if primary_match:
                job_titles.extend(self._extract_titles_from_section(primary_match.group(1)))

            # Extract secondary job titles (old format)
            secondary_match = re.search(
                r'### Secondary Interest:.*?\n(.*?)(?=###|\n## )',
                content,
                re.DOTALL
            )
            if secondary_match:
                job_titles.extend(self._extract_titles_from_section(secondary_match.group(1)))

            # Extract also consider titles (old format)
            also_match = re.search(
                r'### Also Consider\n(.*?)(?=\n## )',
                content,
                re.DOTALL
            )
            if also_match:
                job_titles.extend(self._extract_titles_from_section(also_match.group(1)))

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

    def _extract_titles_from_section(self, section_text: str) -> List[str]:
        """
        Extract job titles from a markdown section.

        Filters out description lines (lines starting with common words like
        'Your', 'Focus', 'These', etc.).

        Args:
            section_text: Text content of a section

        Returns:
            List of job titles
        """
        titles = []
        skip_prefixes = (
            'Your', 'Focus', 'These', 'Strong', 'Reliable', 'Broader',
            'your', 'focus', 'these', 'strong', 'reliable', 'broader',
        )

        for line in section_text.strip().split('\n'):
            line = line.strip()
            if line.startswith('- '):
                title = line[2:].strip()
                # Skip description lines
                if title and not title.startswith(skip_prefixes):
                    titles.append(title)

        return titles

    def generate_instructions(
        self,
        output_dir: str = "instructions",
        filename: Optional[str] = None,
        mode: str = "standard",
    ) -> Dict[str, Any]:
        """
        Generate complete Antigravity instruction JSON file.

        Creates INDEPENDENT search tasks for each job title to ensure
        comprehensive coverage across all target positions.

        Args:
            output_dir: Directory to save instruction file
            filename: Optional custom filename (defaults to timestamped name)
            mode: Search mode - "quick", "standard", or "full"
                - quick: 2 primary + 1 secondary (~10 min)
                - standard: 5 primary + 4 secondary (~30 min)
                - full: all titles including tertiary (~50 min)

        Returns:
            Dictionary containing the generated instructions
        """
        # Validate mode
        valid_modes = ["quick", "standard", "full"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode '{mode}'. Must be one of: {valid_modes}")

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

        # Categorize job titles by priority based on mode
        job_titles = self.preferences['job_titles']
        categorized_titles = self._categorize_job_titles(job_titles, mode=mode)

        # Build instructions dictionary
        instructions = {
            '_metadata': {
                'generated_at': timestamp,
                'task_type': 'scrape_jobs',
                'version': '2.0',  # Updated version for independent search
                'search_strategy': 'independent_per_title',
                'mode': mode,
            },
            'credentials': self.credentials,
            'search_parameters': {
                'job_titles': job_titles,
                'job_titles_by_priority': categorized_titles,
                'locations': self.preferences['locations'],
                'filters': self.preferences['filters'],
            },
            'platforms': [],
            'search_tasks': [],  # NEW: Independent search tasks
            'data_schema': DATA_SCHEMA,
        }

        # Generate platform-specific instructions
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)

        locations_str = ', '.join(self.preferences['locations'])

        for platform in self.preferences['enabled_platforms']:
            if platform not in self.credentials:
                print(f"Warning: No credentials found for {platform}, skipping...")
                continue

            platform_creds = self.credentials[platform]

            # Generate INDEPENDENT search task for each job title
            for priority, titles in categorized_titles.items():
                for title in titles:
                    task_id = f"{platform}_{title.lower().replace(' ', '_')}"

                    instruction_params = {
                        'email': platform_creds.get('email', ''),
                        'password': platform_creds.get('password', '***'),
                        'job_titles': title,  # Single title per search
                        'locations': locations_str,
                        'remote_only': self.preferences['filters']['remote_only'],
                        'min_salary': self.preferences['filters']['min_salary'],
                        'visa_sponsorship_required': self.preferences['filters']['visa_sponsorship_required'],
                        'output_file': str(data_dir / f"{platform}_{title.lower().replace(' ', '_')}.json"),
                    }

                    instruction_text = get_platform_instruction(platform, **instruction_params)

                    search_task = {
                        'task_id': task_id,
                        'platform': platform,
                        'job_title': title,
                        'priority': priority,
                        'max_pages': 5 if priority == 'primary' else 3,  # More pages for primary
                        'instructions': instruction_text,
                        'output_file': instruction_params['output_file'],
                    }

                    instructions['search_tasks'].append(search_task)

            # Also add platform summary for backward compatibility
            platform_config = {
                'name': platform,
                'priority': PLATFORM_PRIORITY.get(platform, 'medium'),
                'total_searches': len([t for t in instructions['search_tasks'] if t['platform'] == platform]),
                'output_dir': str(data_dir),
            }
            instructions['platforms'].append(platform_config)

        # Generate summary
        total_tasks = len(instructions['search_tasks'])
        instructions['_summary'] = {
            'mode': mode,
            'total_search_tasks': total_tasks,
            'platforms': len(instructions['platforms']),
            'primary_titles': len(categorized_titles.get('primary', [])),
            'secondary_titles': len(categorized_titles.get('secondary', [])),
            'tertiary_titles': len(categorized_titles.get('tertiary', [])),
            'estimated_time_minutes': total_tasks * 3,  # ~3 min per search (conservative)
        }

        # Save to file
        output_file = output_path / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(instructions, f, indent=2, ensure_ascii=False)

        print(f"Generated instruction file: {output_file}")
        print(f"Total search tasks: {instructions['_summary']['total_search_tasks']}")
        print(f"Estimated time: ~{instructions['_summary']['estimated_time_minutes']} minutes")

        return {
            'instructions': instructions,
            'output_file': str(output_file),
        }

    def _categorize_job_titles(
        self,
        job_titles: List[str],
        mode: str = "standard"
    ) -> Dict[str, List[str]]:
        """
        Categorize job titles by priority based on search mode.

        Modes:
        - quick: 2 primary + 1 secondary (fast, ~10 min)
        - standard: 5 primary + 4 secondary (balanced, ~30 min)
        - full: all titles including tertiary (comprehensive, ~50 min)

        Returns:
            Dictionary with 'primary', 'secondary', 'tertiary' keys
        """
        # Full list boundaries
        primary_count = 5
        secondary_count = 4

        all_primary = job_titles[:primary_count]
        all_secondary = job_titles[primary_count:primary_count + secondary_count]
        all_tertiary = job_titles[primary_count + secondary_count:]

        if mode == "quick":
            # Quick mode: 2 primary + 1 secondary
            return {
                'primary': all_primary[:2],
                'secondary': all_secondary[:1],
                'tertiary': [],
            }
        elif mode == "standard":
            # Standard mode: all primary + all secondary
            return {
                'primary': all_primary,
                'secondary': all_secondary,
                'tertiary': [],
            }
        else:  # full
            # Full mode: everything
            return {
                'primary': all_primary,
                'secondary': all_secondary,
                'tertiary': all_tertiary,
            }

    def generate_sample(self, output_file: str = "instructions/scrape_jobs_example.json"):
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
    import sys

    # Parse mode from command line
    mode = "standard"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["quick", "standard", "full"]:
            mode = arg
        elif arg in ["-h", "--help"]:
            print("Usage: python -m src.agents.instruction_generator [mode]")
            print("")
            print("Modes:")
            print("  quick    - 2 primary + 1 secondary titles (~10 min)")
            print("  standard - 5 primary + 4 secondary titles (~30 min, default)")
            print("  full     - All titles including tertiary (~50 min)")
            return
        else:
            print(f"Unknown mode: {arg}. Using 'standard'.")

    generator = InstructionGenerator()

    print("Reading preferences from config/preferences.md...")
    preferences = generator.read_preferences()
    print(f"Found {len(preferences['job_titles'])} job titles")
    print(f"Locations: {', '.join(preferences['locations'])}")
    print(f"Enabled platforms: {', '.join(preferences['enabled_platforms'])}")

    print("\nReading credentials from config/credentials.md...")
    credentials = generator.read_credentials()
    print(f"Found credentials for: {', '.join(credentials.keys())}")

    print(f"\nGenerating Antigravity instructions (mode: {mode})...")
    result = generator.generate_instructions(mode=mode)

    summary = result['instructions']['_summary']
    print(f"\nSuccess! Generated instruction file:")
    print(f"  {result['output_file']}")
    print(f"\nSummary:")
    print(f"  Mode: {summary['mode']}")
    print(f"  Search tasks: {summary['total_search_tasks']}")
    print(f"  Estimated time: ~{summary['estimated_time_minutes']} minutes")
    print(f"\nTo run with Antigravity:")
    print(f"  antigravity run {result['output_file']}")


if __name__ == '__main__':
    main()

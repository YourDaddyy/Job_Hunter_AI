"""
MCP tools for Antigravity agent integration.

Provides tools to generate scraping instructions for the Antigravity agent.
"""

import json
from pathlib import Path
from typing import Dict, Any

from ...agents.instruction_generator import InstructionGenerator


async def generate_antigravity_scraping_guide() -> Dict[str, Any]:
    """
    Generate Antigravity scraping instructions from preferences and credentials.

    This tool reads the job search preferences from config/preferences.md
    and platform credentials from config/credentials.md, then generates
    a complete JSON instruction file for the Antigravity agent to scrape
    jobs from multiple platforms.

    Returns:
        Dictionary with status, instruction file path, and next steps
    """
    try:
        # Initialize generator
        generator = InstructionGenerator()

        # Read preferences
        preferences = generator.read_preferences()
        print(f"Loaded preferences with {len(preferences['job_titles'])} job titles")

        # Read credentials
        credentials = generator.read_credentials()
        print(f"Loaded credentials for {len(credentials)} platforms")

        # Generate instructions
        result = generator.generate_instructions()

        instruction_file = result['output_file']

        return {
            'status': 'success',
            'instruction_file': instruction_file,
            'platforms': [p['name'] for p in result['instructions']['platforms']],
            'job_titles_count': len(preferences['job_titles']),
            'message': f"Generated Antigravity instructions. Run: antigravity run {instruction_file}",
            'next_steps': [
                f"1. Review the instruction file: {instruction_file}",
                f"2. Run Antigravity: antigravity run {instruction_file}",
                "3. After scraping completes, import results with the JSON importer tool",
            ]
        }

    except FileNotFoundError as e:
        return {
            'status': 'error',
            'error': f"Configuration file not found: {str(e)}",
            'message': "Please ensure config/preferences.md and config/credentials.md exist",
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f"Failed to generate instructions: {str(e)}",
        }


async def preview_antigravity_instructions() -> Dict[str, Any]:
    """
    Preview what will be generated without creating files.

    Returns a summary of the instructions that would be generated,
    useful for checking preferences before generating the full file.

    Returns:
        Dictionary with preview information
    """
    try:
        generator = InstructionGenerator()

        # Read preferences
        preferences = generator.read_preferences()

        # Read credentials
        credentials = generator.read_credentials()

        # Get enabled platforms with credentials
        available_platforms = [
            platform for platform in preferences['enabled_platforms']
            if platform in credentials
        ]

        return {
            'status': 'success',
            'preview': {
                'job_titles': preferences['job_titles'],
                'locations': preferences['locations'],
                'filters': preferences['filters'],
                'platforms': available_platforms,
                'platforms_count': len(available_platforms),
            },
            'message': f"Ready to generate instructions for {len(available_platforms)} platforms",
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f"Failed to preview: {str(e)}",
        }


async def list_antigravity_instructions() -> Dict[str, Any]:
    """
    List all generated Antigravity instruction files.

    Returns:
        Dictionary with list of instruction files and their details
    """
    try:
        instructions_dir = Path("W:\\Code\\job_viewer\\instructions")

        if not instructions_dir.exists():
            return {
                'status': 'success',
                'files': [],
                'message': 'No instruction files found (instructions directory does not exist)',
            }

        # Find all JSON files in instructions directory
        json_files = list(instructions_dir.glob("scrape_jobs_*.json"))

        files_info = []
        for file_path in sorted(json_files, reverse=True):  # Most recent first
            # Read metadata
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata = data.get('_metadata', {})
            platforms = [p['name'] for p in data.get('platforms', [])]

            files_info.append({
                'filename': file_path.name,
                'path': str(file_path),
                'generated_at': metadata.get('generated_at', 'unknown'),
                'platforms': platforms,
                'size_kb': file_path.stat().st_size / 1024,
            })

        return {
            'status': 'success',
            'files': files_info,
            'count': len(files_info),
            'message': f"Found {len(files_info)} instruction file(s)",
        }

    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'message': f"Failed to list files: {str(e)}",
        }


# Tool registration for MCP server
def register_tools(server):
    """
    Register Antigravity tools with the MCP server.

    Args:
        server: MCP server instance
    """

    @server.tool()
    async def generate_antigravity_scraping_guide() -> dict:
        """
        Generate Antigravity scraping instructions from preferences.

        Reads config/preferences.md and config/credentials.md to create
        a complete JSON instruction file for scraping jobs from multiple platforms.

        Returns:
            {
                "status": "success",
                "instruction_file": "instructions/scrape_jobs_2026-01-28.json",
                "platforms": ["linkedin", "indeed", "wellfound"],
                "message": "Please run: antigravity run {instruction_file}"
            }
        """
        return await globals()['generate_antigravity_scraping_guide']()

    @server.tool()
    async def preview_antigravity_instructions() -> dict:
        """
        Preview Antigravity instructions without generating files.

        Returns a summary of job titles, locations, filters, and platforms
        that would be included in the generated instructions.

        Returns:
            {
                "status": "success",
                "preview": {
                    "job_titles": [...],
                    "locations": [...],
                    "filters": {...},
                    "platforms": [...]
                }
            }
        """
        return await globals()['preview_antigravity_instructions']()

    @server.tool()
    async def list_antigravity_instructions() -> dict:
        """
        List all generated Antigravity instruction files.

        Returns information about previously generated instruction files
        including their creation dates and target platforms.

        Returns:
            {
                "status": "success",
                "files": [{
                    "filename": "scrape_jobs_2026-01-28.json",
                    "path": "...",
                    "generated_at": "...",
                    "platforms": [...]
                }]
            }
        """
        return await globals()['list_antigravity_instructions']()

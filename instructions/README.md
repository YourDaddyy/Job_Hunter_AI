# Antigravity Scraping Instructions

This directory contains JSON instruction files for the Antigravity agent to scrape jobs from multiple platforms.

## Files

- `scrape_jobs_example.json` - Sample instruction file showing the expected structure
- `scrape_jobs_YYYY-MM-DD.json` - Generated instruction files (timestamped)

## How to Use

### 1. Generate Instructions

Use the instruction generator to create a new instruction file from your preferences:

```python
# Via Python
from src.agents.instruction_generator import InstructionGenerator

generator = InstructionGenerator()
result = generator.generate_instructions()
print(f"Generated: {result['output_file']}")
```

Or via the command line:

```bash
python -m src.agents.instruction_generator
```

Or via MCP tool (from Claude):

```
Call the generate_antigravity_scraping_guide tool
```

### 2. Run with Antigravity

Once you have a generated instruction file, run it with the Antigravity agent:

```bash
antigravity run instructions/scrape_jobs_2026-01-28.json
```

The Antigravity agent will:
1. Read the credentials and search parameters
2. Follow the platform-specific instructions
3. Scrape jobs from each platform
4. Save results to the specified output files in `data/`

### 3. Import Results

After Antigravity completes scraping, import the results into the database:

```python
# Use the JSON importer tool (to be implemented)
# This will parse the scraped JSON files and insert jobs into the database
```

## Instruction File Structure

```json
{
  "_metadata": {
    "generated_at": "timestamp",
    "task_type": "scrape_jobs",
    "version": "1.0"
  },
  "credentials": {
    "platform_name": {
      "email": "...",
      "password": "..."
    }
  },
  "search_parameters": {
    "job_titles": [...],
    "locations": [...],
    "filters": {...}
  },
  "platforms": [
    {
      "name": "platform_name",
      "priority": "high|medium|low",
      "instructions": "Natural language instructions...",
      "output_file": "path/to/output.json"
    }
  ],
  "data_schema": {
    "required_fields": [...],
    "optional_fields": [...]
  }
}
```

## Supported Platforms

- **LinkedIn** (priority: high)
- **Wellfound/AngelList** (priority: high)
- **Indeed** (priority: medium)
- **Glassdoor** (priority: low)

## Security Notes

- Instruction files contain actual credentials from `config/credentials.md`
- Keep these files secure and do not commit them to version control
- The `.gitignore` should exclude `instructions/scrape_jobs_*.json`

## Customization

To customize the scraping instructions:

1. Edit `config/preferences.md` to change:
   - Target job titles
   - Locations
   - Filters (remote, salary, etc.)

2. Edit `config/credentials.md` to update platform credentials

3. Regenerate the instruction file

4. Advanced: Modify `src/agents/platform_configs.py` to change platform-specific instructions

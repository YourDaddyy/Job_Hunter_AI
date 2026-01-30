"""
Test script for Antigravity Instruction Generator.

This script tests the instruction generator by:
1. Reading preferences and credentials
2. Generating JSON instructions
3. Verifying the structure and content
"""

import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.instruction_generator import InstructionGenerator


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_read_preferences():
    """Test reading preferences from config/preferences.md."""
    print_section("Test 1: Reading Preferences")

    try:
        generator = InstructionGenerator()
        preferences = generator.read_preferences()

        print(f"\nJob Titles ({len(preferences['job_titles'])} found):")
        for i, title in enumerate(preferences['job_titles'][:10], 1):
            print(f"  {i}. {title}")
        if len(preferences['job_titles']) > 10:
            print(f"  ... and {len(preferences['job_titles']) - 10} more")

        print(f"\nLocations ({len(preferences['locations'])} found):")
        for loc in preferences['locations']:
            print(f"  - {loc}")

        print(f"\nFilters:")
        for key, value in preferences['filters'].items():
            print(f"  - {key}: {value}")

        print(f"\nEnabled Platforms ({len(preferences['enabled_platforms'])} found):")
        for platform in preferences['enabled_platforms']:
            print(f"  - {platform}")

        print("\n[OK] Preferences read successfully!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error reading preferences: {e}")
        return False


def test_read_credentials():
    """Test reading credentials from config/credentials.md."""
    print_section("Test 2: Reading Credentials")

    try:
        generator = InstructionGenerator()
        credentials = generator.read_credentials()

        print(f"\nPlatforms with credentials ({len(credentials)} found):")
        for platform, creds in credentials.items():
            email = creds.get('email', 'N/A')
            has_password = 'Yes' if creds.get('password') else 'No'
            login_method = creds.get('login_method', 'email')

            print(f"\n  {platform}:")
            print(f"    Email: {email}")
            print(f"    Password: {'***' if has_password == 'Yes' else 'Not set'}")
            if 'login_method' in creds:
                print(f"    Login Method: {login_method}")

        print("\n[OK] Credentials read successfully!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error reading credentials: {e}")
        return False


def test_generate_instructions():
    """Test generating complete instruction file."""
    print_section("Test 3: Generating Instructions")

    try:
        generator = InstructionGenerator()

        # Generate instructions to a test directory
        test_output_dir = project_root / "instructions" / "test"
        test_output_dir.mkdir(parents=True, exist_ok=True)

        result = generator.generate_instructions(
            output_dir=str(test_output_dir),
            filename="test_scrape_jobs.json"
        )

        print(f"\nGenerated instruction file:")
        print(f"  Path: {result['output_file']}")

        # Load and verify the file
        with open(result['output_file'], 'r', encoding='utf-8') as f:
            instructions = json.load(f)

        print(f"\nInstruction file structure:")
        print(f"  Metadata: {instructions['_metadata']}")
        print(f"  Platforms: {len(instructions['platforms'])} configured")
        print(f"  Credentials: {len(instructions['credentials'])} platforms")
        print(f"  Search Parameters:")
        print(f"    - Job titles: {len(instructions['search_parameters']['job_titles'])}")
        print(f"    - Locations: {len(instructions['search_parameters']['locations'])}")
        print(f"    - Filters: {instructions['search_parameters']['filters']}")

        print(f"\nPlatform configurations:")
        for platform in instructions['platforms']:
            print(f"  - {platform['name']} (priority: {platform['priority']})")
            print(f"    Output: {platform['output_file']}")
            print(f"    Instructions: {len(platform['instructions'])} characters")

        print("\n[OK] Instructions generated successfully!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error generating instructions: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_json_structure():
    """Test JSON structure validation."""
    print_section("Test 4: Validating JSON Structure")

    try:
        # Load the generated test file
        test_file = project_root / "instructions" / "test" / "test_scrape_jobs.json"

        if not test_file.exists():
            print(f"\n[FAIL] Test file not found: {test_file}")
            return False

        with open(test_file, 'r', encoding='utf-8') as f:
            instructions = json.load(f)

        # Check required fields
        required_top_level = ['_metadata', 'credentials', 'search_parameters', 'platforms', 'data_schema']
        missing_fields = [field for field in required_top_level if field not in instructions]

        if missing_fields:
            print(f"\n[FAIL] Missing required fields: {missing_fields}")
            return False

        print("\n[OK] All required top-level fields present")

        # Validate metadata
        metadata_fields = ['generated_at', 'task_type', 'version']
        metadata = instructions['_metadata']
        missing_metadata = [field for field in metadata_fields if field not in metadata]

        if missing_metadata:
            print(f"\n[FAIL] Missing metadata fields: {missing_metadata}")
            return False

        print("[OK] Metadata structure valid")

        # Validate platform configurations
        if not instructions['platforms']:
            print("\n[FAIL] No platforms configured")
            return False

        for platform in instructions['platforms']:
            required_platform_fields = ['name', 'priority', 'instructions', 'output_file']
            missing_platform_fields = [field for field in required_platform_fields if field not in platform]

            if missing_platform_fields:
                print(f"\n[FAIL] Platform {platform.get('name', 'unknown')} missing fields: {missing_platform_fields}")
                return False

        print(f"[OK] All {len(instructions['platforms'])} platform configurations valid")

        # Validate credentials
        for platform_name in [p['name'] for p in instructions['platforms']]:
            if platform_name not in instructions['credentials']:
                print(f"\n[FAIL] Missing credentials for platform: {platform_name}")
                return False

            creds = instructions['credentials'][platform_name]
            if 'email' not in creds:
                print(f"\n[FAIL] Missing email in credentials for {platform_name}")
                return False

        print(f"[OK] Credentials present for all platforms")

        # Validate data schema
        schema = instructions['data_schema']
        if 'required_fields' not in schema or 'optional_fields' not in schema:
            print("\n[FAIL] Data schema missing required or optional fields")
            return False

        print(f"[OK] Data schema valid ({len(schema['required_fields'])} required, {len(schema['optional_fields'])} optional)")

        print("\n[OK] All JSON structure validation passed!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error validating structure: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generate_sample():
    """Test generating the example file."""
    print_section("Test 5: Generating Sample/Example File")

    try:
        generator = InstructionGenerator()

        # Generate the example file
        result = generator.generate_sample()

        print(f"\nGenerated example file:")
        print(f"  Path: {result['output_file']}")

        # Verify file exists
        example_file = Path(result['output_file'])
        if not example_file.exists():
            print(f"\n[FAIL] Example file not created")
            return False

        file_size = example_file.stat().st_size / 1024
        print(f"  Size: {file_size:.2f} KB")

        print("\n[OK] Example file generated successfully!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Error generating example: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  Antigravity Instruction Generator - Test Suite")
    print("=" * 80)

    tests = [
        ("Read Preferences", test_read_preferences),
        ("Read Credentials", test_read_credentials),
        ("Generate Instructions", test_generate_instructions),
        ("Validate JSON Structure", test_json_structure),
        ("Generate Sample File", test_generate_sample),
    ]

    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))

    # Summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "[OK] PASS" if result else "[FAIL] FAIL"
        print(f"  {status}: {test_name}")

    print(f"\n  Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n  All tests passed!")
        return 0
    else:
        print("\n  Some tests failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

"""
Platform-specific instruction templates for Antigravity agent.

This module defines natural language instructions for scraping jobs from various platforms.
"""

PLATFORM_INSTRUCTIONS = {
    'linkedin': """
1. Navigate to LinkedIn Jobs (https://www.linkedin.com/jobs/)
2. If login is required:
   - Click "Sign in" button
   - Enter email: {email}
   - Enter password: {password}
   - Click "Sign in" to complete login
   - Wait for page to load completely
3. In the search box:
   - Enter job title keywords: {job_titles}
   - Enter location: {locations}
   - Click "Search" button
4. Apply filters on the left sidebar:
   - Click "Remote" filter if remote_only is true
   - If min_salary is specified, use salary filter
   - If visa_sponsorship_required, look for relevant filters
5. For each page (max 10 pages):
   - Scroll down to load all job cards
   - For each job card visible on the page:
     a. Extract job title
     b. Extract company name
     c. Extract location
     d. Extract job URL/link
     e. Click on the job card to open full description
     f. Extract full job description text
     g. Extract salary if shown
     h. Check if "Easy Apply" badge is present
     i. Extract posted date (e.g., "2 days ago")
     j. Go back to search results
   - Click "Next" or scroll to load more results
   - Stop if "Next" button is disabled or after 10 pages
6. Save all extracted data to: {output_file}
7. Format: JSON array with objects containing required fields
""",

    'indeed': """
1. Navigate to Indeed (https://www.indeed.com/)
2. If login is required and login_method is not 'google':
   - Click "Sign in" button
   - Enter email: {email}
   - Enter password: {password}
   - Click "Sign in" to complete login
3. If login_method is 'google':
   - Click "Continue with Google" button
   - Select account: {email}
   - Complete Google authentication flow
4. In the search form:
   - Enter "What" field: {job_titles}
   - Enter "Where" field: {locations}
   - Click "Search" button
5. Apply filters:
   - If remote_only: Click "Remote" filter option
   - If min_salary: Use salary range filter
6. For each page (max 10 pages):
   - For each job card:
     a. Extract job title
     b. Extract company name
     c. Extract location
     d. Extract job URL
     e. Click job title to view full description
     f. Extract complete job description
     g. Extract salary if displayed
     h. Check for "Easily apply" badge
     i. Extract posted date
     j. Return to search results
   - Click "Next" pagination button
   - Stop after 10 pages or when no more results
7. Save data to: {output_file}
8. Format: JSON array with required fields
""",

    'wellfound': """
1. Navigate to Wellfound (https://wellfound.com/jobs)
2. If login required:
   - Click "Log in" button
   - Enter email: {email}
   - Enter password: {password}
   - Click "Log in" to complete authentication
   - Wait for dashboard to load
3. In the job search interface:
   - Use search bar to enter: {job_titles}
   - Set location filter to: {locations}
4. Apply filters:
   - Click "Remote OK" or "Remote" filter if remote_only is true
   - Use salary filter if min_salary is specified
   - Look for "Visa Sponsorship" filter if visa_sponsorship_required
5. Scroll through job listings:
   - Wellfound uses infinite scroll, so scroll down to load more
   - For each job card:
     a. Extract job title
     b. Extract company name
     c. Extract location/remote status
     d. Extract job URL/link
     e. Click to open job details
     f. Extract full job description
     g. Extract salary range if shown
     h. Extract equity/benefits information
     i. Check for "Easy Apply" or "Apply on Wellfound" option
     j. Extract posted date
     k. Return to search results
   - Continue scrolling until 100 jobs collected or no more results
6. Save data to: {output_file}
7. Format: JSON array with required fields plus equity/benefits if available
""",

    'glassdoor': """
1. Navigate to Glassdoor Jobs (https://www.glassdoor.com/Job/)
2. If login required (may be needed to view full details):
   - Click "Sign In" button
   - Enter email: {email}
   - Enter password: {password}
   - Click "Sign In" to complete login
   - Handle any pop-ups or prompts
3. In the search interface:
   - Enter job title in "Search jobs" field: {job_titles}
   - Enter location in "Location" field: {locations}
   - Click "Search" button
4. Apply filters:
   - If remote_only: Select "Remote" in location type filter
   - Use salary filter if min_salary is specified
   - Apply other relevant filters
5. For each page (max 10 pages):
   - For each job listing:
     a. Extract job title
     b. Extract company name
     c. Extract location
     d. Extract job URL
     e. Click job to view details
     f. Extract full job description
     g. Extract salary estimate if shown
     h. Extract company rating
     i. Check for "Easy Apply" option
     j. Extract posted date
     k. Return to search results
   - Click "Next" or page number to navigate
   - Stop after 10 pages or no more results
6. Save data to: {output_file}
7. Format: JSON array with required fields plus company rating
""",
}


def get_platform_instruction(platform_name: str, **kwargs) -> str:
    """
    Get instruction template for a specific platform and format it with parameters.

    Args:
        platform_name: Name of the platform (linkedin, indeed, wellfound, glassdoor)
        **kwargs: Parameters to format the instruction template

    Returns:
        Formatted instruction string

    Raises:
        KeyError: If platform_name is not found
    """
    template = PLATFORM_INSTRUCTIONS.get(platform_name.lower())
    if template is None:
        raise KeyError(f"Platform '{platform_name}' not found in PLATFORM_INSTRUCTIONS")

    return template.format(**kwargs)


# Platform priority mapping (higher is more important)
PLATFORM_PRIORITY = {
    'linkedin': 'high',
    'wellfound': 'high',
    'indeed': 'medium',
    'glassdoor': 'low',
}


# Data schema for scraped jobs
DATA_SCHEMA = {
    'required_fields': [
        'title',
        'company',
        'url',
        'description',
    ],
    'optional_fields': [
        'salary',
        'location',
        'posted_date',
        'easy_apply',
        'remote',
        'company_rating',
        'equity',
        'benefits',
    ]
}

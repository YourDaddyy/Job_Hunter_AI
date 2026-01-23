# Job Search Preferences

## Target Positions

List job titles you're interested in:

- [Job Title 1, e.g., "AI Engineer"]
- [Job Title 2, e.g., "Backend Engineer"]
- [Job Title 3, e.g., "Software Engineer"]
- [Add more as needed]

## Location Requirements

### Preferred
- [e.g., "Remote (fully remote)"]
- [e.g., "United States (remote)"]
- [e.g., "Canada (remote)"]

### Acceptable
- [e.g., "Hybrid (max 2 days/week in office)"]

### Not Acceptable
- [e.g., "Onsite only"]
- [e.g., "Relocation required"]

## Work Authorization

- Current Status: [e.g., "Work Permit (Canada)", "H1B", "Green Card", "Citizen"]
- Requires Visa Sponsorship: [Yes/No]
- Willing to Relocate: [Yes/No/Conditional]

## Salary Expectations

- Minimum: $[amount] [currency]/year
- Target: $[min] - $[max] [currency]/year
- Currency: [USD/CAD/EUR/etc.]
- Note: [Optional notes, e.g., "Open to discussion for exceptional roles"]

## Company Preferences

### Blacklist (Do not apply)

Companies or types of companies to avoid:

- [Company name 1]
- [Company name 2]
- [e.g., "Any staffing/consulting agency"]

### Preferred Company Types

- [e.g., "Product companies"]
- [e.g., "AI-focused startups (Series A+)"]
- [e.g., "Tech giants with AI teams"]

## Keyword Filters

### Must NOT contain (auto-reject)

Jobs containing these keywords will be automatically rejected:

- "clearance required"
- "security clearance"
- "US citizen only"
- "no sponsorship"
- [Add your own]

### Preferred keywords (bonus points)

Jobs with these keywords get higher match scores:

- "visa sponsorship available"
- "remote friendly"
- [Add your own]

## Application Settings

### Decision Thresholds

- auto_apply_threshold: 0.85    # Score >= 85% -> auto apply
- notify_threshold: 0.60        # Score 60-85% -> ask user
- reject_threshold: 0.60        # Score < 60% -> auto reject

### Rate Limits

- max_applications_per_day: 20
- max_applications_per_hour: 5
- scrape_interval_hours: 4      # How often to check for new jobs

### Platforms

Enable/disable job platforms:

- linkedin: enabled
- indeed: enabled
- wellfound: enabled

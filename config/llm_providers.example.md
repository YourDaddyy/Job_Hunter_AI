# LLM Provider Configuration

> Configure which LLM providers to use for filtering and resume generation.
> Copy this file to `llm_providers.md` and customize settings.

## Active Providers

### Filtering Provider
- Provider: glm
- Model: glm-4-flash
- Purpose: Job filtering (cost-effective, ~$0.001/job)

### Resume Provider
- Provider: glm
- Model: glm-4-flash
- Purpose: Resume tailoring (cost-effective, ~$0.003/resume)

## Available Providers

### GLM (智谱AI) - Default
- API Key Env: GLM_API_KEY
- Base URL: https://open.bigmodel.cn/api/paas/v4
- Models: glm-4-flash (recommended), glm-4-plus
- Pricing: ~$0.001/1K tokens
- Notes: Best balance of cost and quality for Chinese + English content

### OpenAI
- API Key Env: OPENAI_API_KEY
- Models: gpt-4o, gpt-4o-mini (recommended), gpt-4-turbo
- Pricing: $0.00015-0.03/1K tokens (varies by model)
- Notes: Best overall quality, higher cost

### Google Gemini
- API Key Env: GOOGLE_API_KEY
- Models: gemini-2.0-flash (recommended), gemini-1.5-pro
- Pricing: ~$0.001/1K tokens
- Notes: Fast and cost-effective

### Anthropic Claude
- API Key Env: ANTHROPIC_API_KEY
- Models: claude-sonnet-4-20250514
- Pricing: $0.003-0.015/1K tokens
- Notes: Excellent for writing tasks, premium quality

### MiniMax
- API Key Env: MINIMAX_API_KEY
- Models: abab6.5s-chat
- Pricing: ~$0.002/1K tokens
- Notes: Good for Chinese market applications

### OpenRouter (Unified Gateway)
- API Key Env: OPENROUTER_API_KEY
- Models: Any model via openrouter.ai (e.g., anthropic/claude-sonnet-4)
- Pricing: Varies by model
- Notes: Access 100+ models with single API key, useful for experimentation

## Example Configurations

### Budget-Friendly (Default)
```
Filtering: glm / glm-4-flash
Resume: glm / glm-4-flash
Cost: ~$0.15 for 120 jobs + 8 resumes
```

### Quality-Focused
```
Filtering: glm / glm-4-flash
Resume: openai / gpt-4o
Cost: ~$0.30 for 120 jobs + 8 resumes
```

### Premium
```
Filtering: openai / gpt-4o-mini
Resume: claude / claude-sonnet-4-20250514
Cost: ~$0.50 for 120 jobs + 8 resumes
```

### OpenRouter Unified
```
Filtering: openrouter / google/gemini-2.0-flash
Resume: openrouter / anthropic/claude-sonnet-4
Cost: Varies
```

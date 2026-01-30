# LLM Provider Configuration

> **Note:** API keys are read from `.env` file (e.g. `OPENAI_API_KEY`, `GOOGLE_API_KEY`).

## Active Providers

### Filtering Provider
- Provider: glm
- Model: glm-4-flash
- Purpose: Job filtering (cost-effective)

### Resume Provider
- Provider: glm
- Model: glm-4-flash
- Purpose: Resume tailoring (defaults to cost-effective GLM, change to 'openai' or 'anthropic' for higher quality)

## Available Providers

### GLM (智谱AI)
- API Key Env: GLM_API_KEY
- Base URL: https://open.bigmodel.cn/api/paas/v4
- Models: glm-4-flash, glm-4-plus
- Notes: Best for Chinese + English content integration

### OpenAI
- API Key Env: OPENAI_API_KEY
- Models: gpt-4o, gpt-4o-mini, gpt-4-turbo
- Notes: Industry standard for reasoning and quality

### Google Gemini
- API Key Env: GOOGLE_API_KEY
- Models: gemini-2.0-flash, gemini-1.5-pro
- Notes: High speed and large context window

### Anthropic Claude
- API Key Env: ANTHROPIC_API_KEY
- Models: claude-3-5-sonnet-20240620
- Notes: Excellent for writing natural, human-like resumes

### OpenRouter (Unified Gateway)
- API Key Env: OPENROUTER_API_KEY
- Models: Any model ID (e.g., "anthropic/claude-3-opus", "meta/llama-3-70b")
- Notes: Unified access to 100+ models

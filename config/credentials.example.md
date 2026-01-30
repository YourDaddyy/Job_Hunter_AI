# Platform Credentials

> **IMPORTANT**: Copy this file to `credentials.md` and fill in your actual credentials.
> **NEVER** commit `credentials.md` to version control!

---

## Job Platforms

### LinkedIn

```yaml
platform: linkedin
email: your-email@example.com
password: your-password
```

### Indeed

```yaml
platform: indeed
email: your-email@example.com
password: your-password
```

### Wellfound (AngelList)

```yaml
platform: wellfound
email: your-email@example.com
password: your-password
```

### Glassdoor

```yaml
platform: glassdoor
email: your-email@example.com
password: your-password
```

---

## API Keys

### GLM (Job Filtering)

```yaml
service: glm
api_key: your-glm-api-key
api_url: https://open.bigmodel.cn/api/paas/v4
```

### Anthropic (Resume Tailoring)

```yaml
service: anthropic
api_key: sk-ant-your-anthropic-key
```

### Telegram (Notifications)

```yaml
service: telegram
bot_token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
chat_id: your-chat-id
```

---

## Optional Settings

### Proxy (Anti-Detection)

```yaml
service: proxy
url: http://user:pass@proxy:port
enabled: false
```

---

## How This Works

When you run the job hunter via Claude Code CLI:

1. Claude Code reads `config/credentials.md` via the MCP `credentials://config` resource
2. The credentials are securely passed to the scrapers
3. Each scraper uses the appropriate credentials for login

**Security Notes**:
- Credentials are stored locally only
- Never commit `credentials.md` to git
- The file is in `.gitignore` by default

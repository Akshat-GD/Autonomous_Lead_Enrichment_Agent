# Autonomous_Lead_Enrichment_Agent
SoftwareBrio - AI Eng Intern assignment

A Python pipeline that takes a list of company domains, crawls each site's
public web presence with a headless browser, cleans the content down to
token-efficient Markdown, and uses a locally-hosted LLM (via [Ollama](https://ollama.com))
with strict structured outputs to produce sales-ready company intelligence:

- 2-sentence company overview
- Target audience / ICP
- Public contact emails (contact@, sales@, support@, ...)
- Key leadership / team members (name, role, LinkedIn URL if discoverable)
- A 0.0–1.0 data confidence score
- Per-domain token usage and estimated cost

```
domains  →  Playwright crawl  →  HTML→Markdown cleanup  →  Ollama (structured JSON)  →  output.json / output.csv
                                                                     │
                                                                     └──▶ cost_log.csv (tokens + $ per domain)
```
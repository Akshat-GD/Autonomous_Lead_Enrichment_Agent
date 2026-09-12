from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (no-op if it doesn't exist, e.g. first Colab run)
load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y"}


def _env_list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [v.strip() for v in val.split(",") if v.strip()]


@dataclass
class Settings:
    # --- LLM (Ollama) ---
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    llm_request_timeout: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "180"))

    # Cost is $0 for a locally-hosted Ollama model. These knobs exist so the
    # exact same cost_tracker code path works if OLLAMA_HOST is later pointed
    # at a hosted/paid endpoint, or swapped for a paid-API extractor.
    cost_per_1k_prompt_tokens: float = float(os.getenv("COST_PER_1K_PROMPT_TOKENS", "0.0"))
    cost_per_1k_completion_tokens: float = float(os.getenv("COST_PER_1K_COMPLETION_TOKENS", "0.0"))

    # --- Crawler ---
    max_subpages_per_domain: int = int(os.getenv("MAX_SUBPAGES_PER_DOMAIN", "6"))
    page_load_timeout_ms: int = int(os.getenv("PAGE_LOAD_TIMEOUT_MS", "25000"))
    request_delay_seconds: float = float(os.getenv("REQUEST_DELAY_SECONDS", "1.0"))
    headless: bool = _env_bool("HEADLESS", True)
    user_agent: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 LeadEnrichmentAgent/1.0",
    )
    subpage_keywords: list[str] = field(
        default_factory=lambda: _env_list(
            "SUBPAGE_KEYWORDS",
            [
                "about", "about-us", "company", "team", "our-team",
                "leadership", "contact", "contact-us", "pricing",
                "careers", "who-we-are",
            ],
        )
    )

    # --- Content limits (token optimization) ---
    max_chars_per_page: int = int(os.getenv("MAX_CHARS_PER_PAGE", "6000"))
    max_chars_total_context: int = int(os.getenv("MAX_CHARS_TOTAL_CONTEXT", "18000"))

    # --- Output ---
    output_dir: Path = Path(os.getenv("OUTPUT_DIR", "output"))
    output_json_name: str = os.getenv("OUTPUT_JSON_NAME", "output.json")
    output_csv_name: str = os.getenv("OUTPUT_CSV_NAME", "output.csv")
    cost_log_name: str = os.getenv("COST_LOG_NAME", "cost_log.csv")

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


settings = Settings()
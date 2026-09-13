from __future__ import annotations

import json
import logging
import time

import httpx
from pydantic import ValidationError

from .config import settings
from .schemas import CompanyIntelligence

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a meticulous B2B sales research analyst. You will be given "
    "Markdown content scraped from a company's public website (homepage "
    "plus subpages such as /about, /team, /contact, /pricing). "
    "Extract ONLY information that is explicitly present in the provided "
    "content. Do not invent names, titles, emails, or URLs. If a field "
    "cannot be found, return an empty list/string as appropriate rather "
    "than guessing.\n\n"
    "confidence_score MUST be a decimal number between 0.0 and 1.0 "
    "(NOT a 1-10 scale, NOT a percentage/0-100 scale). "
    "For example: use 0.9 to mean 'high confidence', never 9 or 90. "
    "Set it based on how much of the requested information was actually "
    "present in the content: 0.9-1.0 if team names, roles, emails and clear "
    "positioning were all found; 0.5-0.7 if only some of those were found; "
    "0.2-0.4 if only generic homepage copy was available."
)


class ExtractionOutcome:
    def __init__(
        self,
        data: CompanyIntelligence | None,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
        error: str | None = None,
    ) -> None:
        self.data = data
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.latency_seconds = latency_seconds
        self.error = error


def _build_user_prompt(domain: str, context_markdown: str, regex_emails: list[str]) -> str:
    hint = ""
    if regex_emails:
        hint = (
            "\n\nA deterministic regex pass over the same pages additionally found "
            f"these candidate public email addresses: {regex_emails}. Cross-check "
            "these against the content and include the genuinely public/generic "
            "ones (contact@, sales@, support@, etc.) in contact_points."
        )
    return (
        f"Company domain: {domain}\n\n"
        f"Scraped website content follows:\n{context_markdown}"
        f"{hint}"
    )


def extract_company_intelligence(
    domain: str, context_markdown: str, regex_emails: list[str]
) -> ExtractionOutcome:
    schema = CompanyIntelligence.model_json_schema()
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(domain, context_markdown, regex_emails)},
        ],
        "format": schema,
        "stream": False,
        "options": {"temperature": settings.llm_temperature},
    }

    start = time.perf_counter()
    try:
        resp = httpx.post(
            f"{settings.ollama_host}/api/chat",
            json=payload,
            timeout=settings.llm_request_timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Ollama request failed for %s: %s", domain, exc)
        return ExtractionOutcome(None, 0, 0, time.perf_counter() - start, error=str(exc))

    body = resp.json()
    latency = time.perf_counter() - start

    prompt_tokens = int(body.get("prompt_eval_count", 0))
    completion_tokens = int(body.get("eval_count", 0))
    raw_content = body.get("message", {}).get("content", "")

    try:
        parsed = CompanyIntelligence.model_validate(json.loads(raw_content))
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.error("Failed to parse/validate LLM output for %s: %s", domain, exc)
        return ExtractionOutcome(
            None, prompt_tokens, completion_tokens, latency, error=f"schema_validation_error: {exc}"
        )

    return ExtractionOutcome(parsed, prompt_tokens, completion_tokens, latency)
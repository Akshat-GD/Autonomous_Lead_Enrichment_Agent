from __future__ import annotations

import asyncio
import csv
import json
import logging
from pathlib import Path

from .config import settings
from .content_cleaner import build_llm_context
from .cost_tracker import CostTracker
from .crawler import crawl_domain
from .llm_extractor import extract_company_intelligence
from .schemas import EnrichmentResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def enrich_domain(domain: str, tracker: CostTracker) -> EnrichmentResult:
    logger.info("=== Processing %s ===", domain)

    try:
        pages = await crawl_domain(domain)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Crawl failed for %s", domain)
        return EnrichmentResult(domain=domain, status="failed", error=f"crawl_error: {exc}")

    if not pages:
        return EnrichmentResult(domain=domain, status="failed", error="no_pages_fetched")

    context_markdown, regex_emails = build_llm_context(pages)
    if not context_markdown:
        return EnrichmentResult(
            domain=domain, status="failed", error="empty_context_after_cleaning",
            pages_crawled=list(pages.keys()),
        )

    outcome = extract_company_intelligence(domain, context_markdown, regex_emails)
    tracker.log(
        domain=domain,
        model=settings.ollama_model,
        prompt_tokens=outcome.prompt_tokens,
        completion_tokens=outcome.completion_tokens,
        latency_seconds=outcome.latency_seconds,
    )

    if outcome.error or outcome.data is None:
        return EnrichmentResult(
            domain=domain,
            status="failed",
            error=outcome.error or "unknown_extraction_error",
            pages_crawled=list(pages.keys()),
            prompt_tokens=outcome.prompt_tokens,
            completion_tokens=outcome.completion_tokens,
            total_tokens=outcome.prompt_tokens + outcome.completion_tokens,
            llm_model=settings.ollama_model,
            latency_seconds=outcome.latency_seconds,
        )

    # Fold in any generic emails the regex safety-net found that the LLM missed.
    merged_emails = sorted(set(outcome.data.contact_points) | set(regex_emails))
    outcome.data.contact_points = merged_emails

    status = "ok" if len(pages) > 1 else "partial"

    return EnrichmentResult(
        domain=domain,
        status=status,
        pages_crawled=list(pages.keys()),
        data=outcome.data,
        prompt_tokens=outcome.prompt_tokens,
        completion_tokens=outcome.completion_tokens,
        total_tokens=outcome.prompt_tokens + outcome.completion_tokens,
        estimated_cost_usd=tracker.records[-1].estimated_cost_usd,
        llm_model=settings.ollama_model,
        latency_seconds=outcome.latency_seconds,
    )


async def run_pipeline(domains: list[str]) -> list[EnrichmentResult]:
    tracker = CostTracker()
    results: list[EnrichmentResult] = []

    for domain in domains:
        result = await enrich_domain(domain, tracker)
        results.append(result)

    out_dir = settings.ensure_output_dir()
    write_json(results, out_dir / settings.output_json_name)
    write_csv(results, out_dir / settings.output_csv_name)
    cost_path = tracker.write_csv()

    totals = tracker.totals()
    logger.info(
        "Done. %s domains | %s total tokens | est. cost $%.6f | cost log: %s",
        totals["total_domains"], totals["total_tokens"],
        totals["total_estimated_cost_usd"], cost_path,
    )
    return results


def write_json(results: list[EnrichmentResult], path: Path) -> None:
    payload = [r.model_dump() for r in results]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def write_csv(results: list[EnrichmentResult], path: Path) -> None:
    fieldnames = [
        "domain", "status", "error", "company_overview", "target_audience",
        "contact_points", "leadership", "confidence_score", "pages_crawled",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "estimated_cost_usd", "llm_model", "latency_seconds",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            data = r.data
            writer.writerow(
                {
                    "domain": r.domain,
                    "status": r.status,
                    "error": r.error or "",
                    "company_overview": data.company_overview if data else "",
                    "target_audience": data.target_audience if data else "",
                    "contact_points": "; ".join(data.contact_points) if data else "",
                    "leadership": "; ".join(
                        f"{m.name} ({m.role}){' - ' + m.linkedin_url if m.linkedin_url else ''}"
                        for m in (data.leadership if data else [])
                    ),
                    "confidence_score": data.confidence_score if data else "",
                    "pages_crawled": "; ".join(r.pages_crawled),
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.total_tokens,
                    "estimated_cost_usd": r.estimated_cost_usd,
                    "llm_model": r.llm_model or "",
                    "latency_seconds": r.latency_seconds,
                }
            )


def run(domains: list[str]) -> list[EnrichmentResult]:
    """Sync entrypoint (handles the asyncio event loop for callers/notebooks)."""
    try:
        return asyncio.run(run_pipeline(domains))
    except RuntimeError:
        # Already inside a running event loop (common in Jupyter/Colab).
        import nest_asyncio  # local import: optional dep, only needed in notebooks

        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(run_pipeline(domains))
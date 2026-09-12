from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import settings


@dataclass
class UsageRecord:
    domain: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_seconds: float
    estimated_cost_usd: float


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    cost = (
        prompt_tokens / 1000 * settings.cost_per_1k_prompt_tokens
        + completion_tokens / 1000 * settings.cost_per_1k_completion_tokens
    )
    return round(cost, 6)


class CostTracker:
    """Accumulates per-domain usage and writes a cost_log.csv at the end."""

    def __init__(self) -> None:
        self.records: list[UsageRecord] = []

    def log(
        self,
        domain: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_seconds: float,
    ) -> UsageRecord:
        record = UsageRecord(
            domain=domain,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_seconds=round(latency_seconds, 2),
            estimated_cost_usd=estimate_cost(prompt_tokens, completion_tokens),
        )
        self.records.append(record)
        return record

    def totals(self) -> dict:
        return {
            "total_domains": len(self.records),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self.records),
            "total_completion_tokens": sum(r.completion_tokens for r in self.records),
            "total_tokens": sum(r.total_tokens for r in self.records),
            "total_estimated_cost_usd": round(sum(r.estimated_cost_usd for r in self.records), 6),
        }

    def write_csv(self, path: Path | None = None) -> Path:
        path = path or (settings.ensure_output_dir() / settings.cost_log_name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "domain", "model", "prompt_tokens", "completion_tokens",
                    "total_tokens", "latency_seconds", "estimated_cost_usd",
                ],
            )
            writer.writeheader()
            for r in self.records:
                writer.writerow(asdict(r))
        return path
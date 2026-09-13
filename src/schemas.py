from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class TeamMember(BaseModel):
    name: str = Field(description="Full name of the leadership/team member")
    role: str = Field(description="Job title or role, e.g. 'CEO & Co-founder'")
    linkedin_url: Optional[str] = Field(
        default=None,
        description="LinkedIn profile URL if present in the page content, else null",
    )


class CompanyIntelligence(BaseModel):
    """The structured object the LLM must return for a single domain."""

    company_overview: str = Field(
        description="A concise 2-sentence summary of what the company does"
    )
    target_audience: str = Field(
        description="Who the product/service is built for, e.g. "
        "'Developers building backend APIs'"
    )
    contact_points: list[str] = Field(
        default_factory=list,
        description="Generic/public email addresses found on the site "
        "(contact@, sales@, support@, etc.)",
    )
    leadership: list[TeamMember] = Field(
        default_factory=list,
        description="Key leadership / team members discoverable on the page content",
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0-1.0 estimate of how complete/reliable this extraction is, "
        "based on how much relevant content was actually found on the site",
    )

    @field_validator("confidence_score", mode="before")
    @classmethod
    def _normalize_confidence_scale(cls, value: Any) -> Any:
        """Self-heal the most common LLM mistake on this field.

        Ollama's `format=<json schema>` constrains the *shape* of the output
        (types, required keys) but does not reliably enforce numeric
        `minimum`/`maximum` bounds during generation — models frequently
        answer a 0-1 "confidence" question on a 1-10 or 0-100 scale instead
        (e.g. returning 8 meaning "8/10"). Rather than dropping the entire
        record over one miscalibrated field, rescale it back into 0.0-1.0.
        Values already in range, or anything we can't sensibly interpret,
        pass through unchanged and let the normal ge=0.0/le=1.0 validation
        catch true errors.
        """
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value

        if 0.0 <= number <= 1.0:
            return number
        if 1.0 < number <= 10.0:
            return number / 10.0
        if 10.0 < number <= 100.0:
            return number / 100.0
        if number < 0.0:
            return 0.0
        return 1.0  # anything larger is clamped to the max rather than rejected


class EnrichmentResult(BaseModel):
    """Final record written to output.json/output.csv for one domain."""

    domain: str
    status: str  # "ok" | "partial" | "failed"
    error: Optional[str] = None
    pages_crawled: list[str] = Field(default_factory=list)
    data: Optional[CompanyIntelligence] = None

    # cost / usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    llm_model: Optional[str] = None
    latency_seconds: float = 0.0
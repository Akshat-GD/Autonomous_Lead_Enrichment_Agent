from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


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
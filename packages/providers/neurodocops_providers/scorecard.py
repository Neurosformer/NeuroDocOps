from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .registry import ProviderKind, ProviderTier


class ProviderRecommendation(str, Enum):
    REJECT = "reject"
    BENCHMARK_MORE = "benchmark_more"
    APPROVE_FOR_EXPERIMENT = "approve_for_experiment"
    APPROVE_FOR_DEFAULT = "approve_for_default"
    DOCUMENT_TYPE_SPECIFIC = "document_type_specific"


class ProviderScorecard(BaseModel):
    provider_name: str = Field(min_length=1)
    provider_kind: ProviderKind
    tier: ProviderTier = ProviderTier.FREE
    benchmark_dataset: str = Field(default="unconfigured", min_length=1)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_score: float = Field(default=0.0, ge=0.0, le=1.0)
    table_score: float = Field(default=0.0, ge=0.0, le=1.0)
    failure_handling_score: float = Field(default=0.0, ge=0.0, le=1.0)
    compliance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    integration_effort_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reviewer_value_score: float = Field(default=0.0, ge=0.0, le=1.0)
    estimated_cost_per_page: float = Field(default=0.0, ge=0.0)
    estimated_cost_per_accepted_packet: float = Field(default=0.0, ge=0.0)
    p50_latency_ms: int | None = Field(default=None, ge=0)
    p95_latency_ms: int | None = Field(default=None, ge=0)
    live_calls_used: bool = False
    notes: str | None = None
    recommendation: ProviderRecommendation = ProviderRecommendation.BENCHMARK_MORE

    def weighted_score(self) -> float:
        return round(
            (
                self.quality_score * 0.30
                + self.citation_score * 0.15
                + self.table_score * 0.10
                + self.failure_handling_score * 0.10
                + self.compliance_score * 0.15
                + self.integration_effort_score * 0.10
                + self.reviewer_value_score * 0.10
            ),
            4,
        )

    def passes_default_gate(self, minimum_score: float = 0.80) -> bool:
        return self.recommendation == ProviderRecommendation.APPROVE_FOR_DEFAULT and self.weighted_score() >= minimum_score


def blank_provider_scorecard(
    provider_name: str,
    provider_kind: ProviderKind,
    tier: ProviderTier = ProviderTier.FREE,
) -> ProviderScorecard:
    return ProviderScorecard(provider_name=provider_name, provider_kind=provider_kind, tier=tier)


def recommend_provider(
    scorecard: ProviderScorecard,
    *,
    default_threshold: float = 0.80,
    experiment_threshold: float = 0.60,
    max_default_cost_per_page: float | None = None,
) -> ProviderRecommendation:
    weighted = scorecard.weighted_score()
    if max_default_cost_per_page is not None and scorecard.estimated_cost_per_page > max_default_cost_per_page:
        return ProviderRecommendation.APPROVE_FOR_EXPERIMENT if weighted >= experiment_threshold else ProviderRecommendation.REJECT
    if weighted >= default_threshold:
        return ProviderRecommendation.APPROVE_FOR_DEFAULT
    if weighted >= experiment_threshold:
        return ProviderRecommendation.APPROVE_FOR_EXPERIMENT
    return ProviderRecommendation.REJECT

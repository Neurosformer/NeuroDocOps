from __future__ import annotations

import time
from collections.abc import Sequence

from pydantic import BaseModel, Field

from packages.domain.neurodocops_domain.models import ClaimDocumentRecord, DocumentType, ExtractedField

from .insurance import ExtractionProvider, OCRProvider
from .registry import ProviderKind, ProviderTier
from .scorecard import ProviderRecommendation, ProviderScorecard, recommend_provider


class ExpectedField(BaseModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class BenchmarkDocument(BaseModel):
    filename: str = Field(min_length=1)
    text: str = Field(min_length=1)
    content_type: str = Field(default="text/plain", min_length=1)
    expected_document_type: DocumentType = DocumentType.UNKNOWN
    expected_fields: list[ExpectedField] = Field(default_factory=list)


class BenchmarkManifest(BaseModel):
    name: str = Field(min_length=1)
    documents: list[BenchmarkDocument] = Field(min_length=1)


class DocumentEvaluationResult(BaseModel):
    filename: str
    expected_document_type: DocumentType
    actual_document_type: DocumentType
    classification_correct: bool
    expected_field_count: int = Field(ge=0)
    matched_field_count: int = Field(ge=0)
    extracted_field_count: int = Field(ge=0)
    citation_count: int = Field(ge=0)
    latency_ms: int = Field(ge=0)


class ProviderEvaluationReport(BaseModel):
    provider_name: str = Field(min_length=1)
    provider_kind: ProviderKind = ProviderKind.OCR
    tier: ProviderTier = ProviderTier.FREE
    benchmark_dataset: str = Field(min_length=1)
    document_count: int = Field(ge=0)
    results: list[DocumentEvaluationResult]
    scorecard: ProviderScorecard


def evaluate_provider_pair(
    *,
    provider_name: str,
    manifest: BenchmarkManifest,
    ocr_provider: OCRProvider,
    extraction_provider: ExtractionProvider,
    tier: ProviderTier = ProviderTier.FREE,
    estimated_cost_per_page: float = 0.0,
    live_calls_used: bool = False,
    compliance_score: float = 1.0,
    integration_effort_score: float = 1.0,
    reviewer_value_score: float | None = None,
) -> ProviderEvaluationReport:
    results: list[DocumentEvaluationResult] = []

    for benchmark_document in manifest.documents:
        started = time.perf_counter()
        document = ClaimDocumentRecord(
            filename=benchmark_document.filename,
            text=benchmark_document.text,
            content_type=benchmark_document.content_type,
        )
        ocr = ocr_provider.parse_document(document)
        document.ocr_provider = ocr.provider
        document.ocr_text = ocr.text
        document.document_type = extraction_provider.classify_document(document, ocr)
        document.extracted_fields = extraction_provider.extract_fields(document, ocr)
        latency_ms = int((time.perf_counter() - started) * 1000)

        matched_fields = _count_matched_fields(benchmark_document.expected_fields, document.extracted_fields)
        citation_count = _count_citations_for_expected_fields(benchmark_document.expected_fields, document.extracted_fields)

        results.append(
            DocumentEvaluationResult(
                filename=benchmark_document.filename,
                expected_document_type=benchmark_document.expected_document_type,
                actual_document_type=document.document_type,
                classification_correct=document.document_type == benchmark_document.expected_document_type,
                expected_field_count=len(benchmark_document.expected_fields),
                matched_field_count=matched_fields,
                extracted_field_count=len(document.extracted_fields),
                citation_count=citation_count,
                latency_ms=latency_ms,
            )
        )

    classification_accuracy = _safe_ratio(sum(1 for result in results if result.classification_correct), len(results))
    expected_field_count = sum(result.expected_field_count for result in results)
    matched_field_count = sum(result.matched_field_count for result in results)
    field_recall = 1.0 if expected_field_count == 0 else _safe_ratio(matched_field_count, expected_field_count)
    citation_score = 0.0 if matched_field_count == 0 else _safe_ratio(
        sum(result.citation_count for result in results),
        matched_field_count,
    )
    quality_score = round(classification_accuracy * 0.4 + field_recall * 0.6, 4)
    latencies = [result.latency_ms for result in results]

    scorecard = ProviderScorecard(
        provider_name=provider_name,
        provider_kind=ProviderKind.OCR,
        tier=tier,
        benchmark_dataset=manifest.name,
        quality_score=quality_score,
        citation_score=round(citation_score, 4),
        table_score=0.0,
        failure_handling_score=1.0,
        compliance_score=compliance_score,
        integration_effort_score=integration_effort_score,
        reviewer_value_score=reviewer_value_score if reviewer_value_score is not None else quality_score,
        estimated_cost_per_page=estimated_cost_per_page,
        estimated_cost_per_accepted_packet=estimated_cost_per_page * len(manifest.documents),
        p50_latency_ms=_percentile_latency(latencies, 50),
        p95_latency_ms=_percentile_latency(latencies, 95),
        live_calls_used=live_calls_used,
    )
    scorecard = scorecard.model_copy(update={"recommendation": recommend_provider(scorecard)})

    return ProviderEvaluationReport(
        provider_name=provider_name,
        benchmark_dataset=manifest.name,
        document_count=len(manifest.documents),
        results=results,
        scorecard=scorecard,
    )


def _count_matched_fields(expected_fields: list[ExpectedField], actual_fields: list[ExtractedField]) -> int:
    actual = {_normalize_field_value(field.name): _normalize_field_value(field.value) for field in actual_fields}
    return sum(
        1
        for expected in expected_fields
        if actual.get(_normalize_field_value(expected.name)) == _normalize_field_value(expected.value)
    )


def _count_citations_for_expected_fields(expected_fields: list[ExpectedField], actual_fields: list[ExtractedField]) -> int:
    matched_names = {
        _normalize_field_value(expected.name)
        for expected in expected_fields
        for actual in actual_fields
        if _normalize_field_value(actual.name) == _normalize_field_value(expected.name)
        and _normalize_field_value(actual.value) == _normalize_field_value(expected.value)
    }
    return sum(
        1
        for actual in actual_fields
        if _normalize_field_value(actual.name) in matched_names and actual.citation.snippet.strip()
    )


def _normalize_field_value(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _percentile_latency(values: Sequence[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((percentile / 100) * (len(ordered) - 1))
    return ordered[index]

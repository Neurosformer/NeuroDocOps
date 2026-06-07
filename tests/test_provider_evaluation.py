from packages.providers.neurodocops_providers import (
    BenchmarkDocument,
    BenchmarkManifest,
    ExpectedField,
    MockOCRProvider,
    ProviderKind,
    ProviderRecommendation,
    ProviderScorecard,
    ProviderTier,
    RuleBasedInsuranceExtractionProvider,
    evaluate_provider_pair,
    recommend_provider,
)
from neurodocops.models import DocumentType


class BadExtractionProvider:
    name = "bad-extraction"

    def classify_document(self, document, ocr):
        return DocumentType.UNKNOWN

    def extract_fields(self, document, ocr):
        return []


def test_provider_evaluation_harness_scores_mock_rule_based_pair() -> None:
    manifest = BenchmarkManifest(
        name="unit-claims-fixture",
        documents=[
            BenchmarkDocument(
                filename="claim-form.pdf",
                text="Claim form for claim number CLM-1001 and policy number POL-42. Loss date 2026-05-01.",
                expected_document_type=DocumentType.CLAIM_FORM,
                expected_fields=[
                    ExpectedField(name="claim_number", value="CLM-1001"),
                    ExpectedField(name="policy_number", value="POL-42"),
                    ExpectedField(name="loss_date", value="2026-05-01"),
                ],
            ),
            BenchmarkDocument(
                filename="repair-invoice.pdf",
                text="Repair invoice. Amount due 1250 USD.",
                expected_document_type=DocumentType.REPAIR_INVOICE,
                expected_fields=[ExpectedField(name="invoice_amount", value="1250 USD")],
            ),
        ],
    )

    report = evaluate_provider_pair(
        provider_name="mock+rule-based-insurance-v0",
        manifest=manifest,
        ocr_provider=MockOCRProvider(),
        extraction_provider=RuleBasedInsuranceExtractionProvider(),
    )

    assert report.benchmark_dataset == "unit-claims-fixture"
    assert report.document_count == 2
    assert all(result.classification_correct for result in report.results)
    assert report.scorecard.quality_score == 1.0
    assert report.scorecard.citation_score == 1.0
    assert report.scorecard.estimated_cost_per_page == 0.0
    assert report.scorecard.live_calls_used is False
    assert report.scorecard.recommendation == ProviderRecommendation.APPROVE_FOR_DEFAULT
    assert report.scorecard.passes_default_gate()


def test_provider_evaluation_rejects_low_quality_provider() -> None:
    manifest = BenchmarkManifest(
        name="unit-claims-fixture",
        documents=[
            BenchmarkDocument(
                filename="claim-form.pdf",
                text="Claim form for claim number CLM-1001.",
                expected_document_type=DocumentType.CLAIM_FORM,
                expected_fields=[ExpectedField(name="claim_number", value="CLM-1001")],
            )
        ],
    )

    report = evaluate_provider_pair(
        provider_name="bad-provider",
        manifest=manifest,
        ocr_provider=MockOCRProvider(),
        extraction_provider=BadExtractionProvider(),
    )

    assert report.scorecard.quality_score < 0.60
    assert report.scorecard.recommendation == ProviderRecommendation.REJECT
    assert report.scorecard.passes_default_gate() is False


def test_provider_recommendation_is_deterministic() -> None:
    strong = ProviderScorecard(
        provider_name="candidate",
        provider_kind=ProviderKind.OCR,
        tier=ProviderTier.CHEAP,
        benchmark_dataset="unit-claims-fixture",
        quality_score=0.95,
        citation_score=0.95,
        table_score=0.8,
        failure_handling_score=1.0,
        compliance_score=0.9,
        integration_effort_score=0.9,
        reviewer_value_score=0.95,
    )
    weak = strong.model_copy(update={"quality_score": 0.1, "citation_score": 0.1, "reviewer_value_score": 0.1})

    assert recommend_provider(strong) == ProviderRecommendation.APPROVE_FOR_DEFAULT
    assert recommend_provider(weak) == ProviderRecommendation.REJECT


def test_provider_recommendation_respects_default_cost_ceiling() -> None:
    scorecard = ProviderScorecard(
        provider_name="expensive-candidate",
        provider_kind=ProviderKind.OCR,
        benchmark_dataset="unit-claims-fixture",
        quality_score=1.0,
        citation_score=1.0,
        table_score=1.0,
        failure_handling_score=1.0,
        compliance_score=1.0,
        integration_effort_score=1.0,
        reviewer_value_score=1.0,
        estimated_cost_per_page=5.0,
    )

    assert recommend_provider(scorecard, max_default_cost_per_page=1.0) == ProviderRecommendation.APPROVE_FOR_EXPERIMENT

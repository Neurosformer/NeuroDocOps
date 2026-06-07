from pathlib import Path

from scripts.run_benchmark_fixture import load_manifest
from packages.providers.neurodocops_providers import MockOCRProvider, RuleBasedInsuranceExtractionProvider, evaluate_provider_pair


def test_auto_claim_benchmark_fixture_runs_with_local_providers() -> None:
    manifest = load_manifest(Path("benchmarks/claim_packets/auto_claim_v1/manifest.json"))

    report = evaluate_provider_pair(
        provider_name="mock-ocr+rule-based-insurance-v0",
        manifest=manifest,
        ocr_provider=MockOCRProvider(),
        extraction_provider=RuleBasedInsuranceExtractionProvider(),
    )

    assert report.benchmark_dataset == "auto_claim_v1"
    assert report.document_count == 4
    assert report.scorecard.live_calls_used is False
    assert report.scorecard.estimated_cost_per_page == 0
    assert all(result.classification_correct for result in report.results)
    assert sum(result.matched_field_count for result in report.results) >= 6

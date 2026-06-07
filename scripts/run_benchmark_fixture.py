from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.domain.neurodocops_domain.models import DocumentType
from packages.providers.neurodocops_providers import (
    BenchmarkDocument,
    BenchmarkManifest,
    ExpectedField,
    MockOCRProvider,
    RuleBasedInsuranceExtractionProvider,
    evaluate_provider_pair,
)


def load_manifest(path: Path) -> BenchmarkManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    base_dir = path.parent
    documents = []
    for raw_document in raw["documents"]:
        text_path = base_dir / raw_document["text_path"]
        documents.append(
            BenchmarkDocument(
                filename=raw_document["filename"],
                text=text_path.read_text(encoding="utf-8"),
                content_type=raw_document.get("content_type", "text/plain"),
                expected_document_type=DocumentType(raw_document.get("expected_document_type", "unknown")),
                expected_fields=[ExpectedField(**field) for field in raw_document.get("expected_fields", [])],
            )
        )
    return BenchmarkManifest(name=raw["name"], documents=documents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local NeuroDocOps benchmark fixture with safe mock/free providers.")
    parser.add_argument(
        "manifest",
        nargs="?",
        default="benchmarks/claim_packets/auto_claim_v1/manifest.json",
        help="Path to a benchmark manifest.json file.",
    )
    args = parser.parse_args()
    manifest = load_manifest(Path(args.manifest))
    report = evaluate_provider_pair(
        provider_name="mock-ocr+rule-based-insurance-v0",
        manifest=manifest,
        ocr_provider=MockOCRProvider(),
        extraction_provider=RuleBasedInsuranceExtractionProvider(),
    )
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

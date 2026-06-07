import json

import pytest

from packages.domain.neurodocops_domain.models import ClaimDocumentRecord
from packages.providers.neurodocops_providers import (
    LocalPDFTextOCRProvider,
    MockOCRProvider,
    ProviderConfigError,
    ProviderKind,
    ProviderRegistry,
    ProviderSettings,
    ProviderTier,
    RuleBasedInsuranceExtractionProvider,
    blank_provider_scorecard,
    create_extraction_provider,
    create_ocr_provider,
    create_provider_registry,
    get_provider_metadata,
    load_provider_settings,
)


def test_provider_registry_defaults_to_free_local_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "NEURODOCOPS_OCR_PROVIDER",
        "NEURODOCOPS_EXTRACTION_PROVIDER",
        "NEURODOCOPS_PROVIDER_TIER",
        "NEURODOCOPS_LIVE_OCR_ENABLED",
        "NEURODOCOPS_MAX_LIVE_OCR_PAGES",
    ]:
        monkeypatch.delenv(name, raising=False)

    registry = create_provider_registry()

    assert registry.settings.provider_tier == ProviderTier.FREE
    assert isinstance(registry.create_ocr_provider(), MockOCRProvider)
    assert isinstance(registry.create_extraction_provider(), RuleBasedInsuranceExtractionProvider)
    assert isinstance(create_ocr_provider(registry.settings), MockOCRProvider)
    assert isinstance(create_extraction_provider(registry.settings), RuleBasedInsuranceExtractionProvider)


def test_provider_settings_can_load_from_mapping() -> None:
    settings = load_provider_settings(
        {
            "NEURODOCOPS_OCR_PROVIDER": " MOCK-OCR ",
            "NEURODOCOPS_EXTRACTION_PROVIDER": " rule-based-insurance-v0 ",
            "NEURODOCOPS_PROVIDER_TIER": "cheap",
            "NEURODOCOPS_LIVE_OCR_ENABLED": "yes",
            "NEURODOCOPS_MAX_LIVE_OCR_PAGES": "10",
            "NEURODOCOPS_OCR_CACHE_ENABLED": "off",
        }
    )

    assert settings.ocr_provider == "mock-ocr"
    assert settings.extraction_provider == "rule-based-insurance-v0"
    assert settings.provider_tier == ProviderTier.CHEAP
    assert settings.live_ocr_enabled is True
    assert settings.max_live_ocr_pages == 10
    assert settings.ocr_cache_enabled is False


def test_provider_registry_rejects_unknown_ocr_provider() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="made-up"))

    with pytest.raises(ProviderConfigError, match="Unsupported NEURODOCOPS_OCR_PROVIDER: made-up"):
        registry.create_ocr_provider()


def test_provider_registry_rejects_unknown_extraction_provider() -> None:
    registry = ProviderRegistry(ProviderSettings(extraction_provider="made-up"))

    with pytest.raises(ProviderConfigError, match="Unsupported NEURODOCOPS_EXTRACTION_PROVIDER: made-up"):
        registry.create_extraction_provider()


def test_provider_registry_blocks_paid_ocr_without_live_flag() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="azure", live_ocr_enabled=False, max_live_ocr_pages=10))

    with pytest.raises(ProviderConfigError, match="NEURODOCOPS_LIVE_OCR_ENABLED=true"):
        registry.create_ocr_provider()


def test_provider_registry_requires_live_ocr_page_budget() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="azure", live_ocr_enabled=True, max_live_ocr_pages=0))

    with pytest.raises(ProviderConfigError, match="NEURODOCOPS_MAX_LIVE_OCR_PAGES > 0"):
        registry.create_ocr_provider()


def test_registered_paid_ocr_provider_fails_until_adapter_exists() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="azure", live_ocr_enabled=True, max_live_ocr_pages=1))

    with pytest.raises(ProviderConfigError, match="registered but no adapter is implemented yet"):
        registry.create_ocr_provider()


def test_registered_free_ocr_provider_fails_until_adapter_exists() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="paddle"))

    with pytest.raises(ProviderConfigError, match="registered but no adapter is implemented yet"):
        registry.create_ocr_provider()


def test_provider_registry_can_create_local_pdf_text_provider() -> None:
    registry = ProviderRegistry(ProviderSettings(ocr_provider="local_pdf_text"))

    provider = registry.create_ocr_provider()

    assert isinstance(provider, LocalPDFTextOCRProvider)
    assert provider.name == "local-pdf-text"


def test_local_pdf_text_provider_extracts_embedded_pdf_text_without_secrets() -> None:
    document = ClaimDocumentRecord(filename="claim-form.pdf", text="fallback wrong text", content_type="application/pdf")
    provider = LocalPDFTextOCRProvider(source_bytes_loader=lambda _: embedded_text_pdf("Claim form with claim number CLM-PDF-1 and policy number POL-PDF."))

    ocr = provider.parse_document(document)
    serialized = json.dumps(ocr.metadata)

    assert ocr.provider == "local-pdf-text"
    assert "CLM-PDF-1" in ocr.text
    assert "fallback wrong text" not in ocr.text
    assert ocr.metadata["source"] == "uploaded_pdf_bytes"
    assert "claim-packets/" not in serialized


def test_local_pdf_text_provider_falls_back_to_payload_text_for_unreadable_pdf() -> None:
    document = ClaimDocumentRecord(filename="scan.pdf", text="fallback claim number CLM-FALLBACK", content_type="application/pdf")
    provider = LocalPDFTextOCRProvider(source_bytes_loader=lambda _: b"%PDF-1.4\nno embedded text")

    ocr = provider.parse_document(document)

    assert ocr.text == "fallback claim number CLM-FALLBACK"
    assert ocr.metadata["source"] == "payload_text"
    assert ocr.metadata["fallback_reason"] == "no_embedded_text"


def test_invalid_provider_tier_fails_clearly() -> None:
    with pytest.raises(ProviderConfigError, match="Unsupported NEURODOCOPS_PROVIDER_TIER: gold"):
        load_provider_settings({"NEURODOCOPS_PROVIDER_TIER": "gold"})


def test_invalid_provider_boolean_fails_clearly() -> None:
    with pytest.raises(ProviderConfigError, match="NEURODOCOPS_LIVE_OCR_ENABLED must be a boolean"):
        load_provider_settings({"NEURODOCOPS_LIVE_OCR_ENABLED": "maybe"})


def test_invalid_provider_budget_fails_clearly() -> None:
    with pytest.raises(ProviderConfigError, match="NEURODOCOPS_MAX_LIVE_OCR_PAGES must be a non-negative integer"):
        load_provider_settings({"NEURODOCOPS_MAX_LIVE_OCR_PAGES": "-1"})


def test_safe_provider_metadata_contains_no_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@example/db")
    monkeypatch.setenv("REDIS_URL", "redis://:secret@example:6379/0")
    monkeypatch.setenv("OBJECT_STORAGE_SECRET_KEY", "super-secret")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "azure-secret")

    serialized = json.dumps(get_provider_metadata())

    assert "postgresql://" not in serialized
    assert "redis://" not in serialized
    assert "super-secret" not in serialized
    assert "azure-secret" not in serialized
    assert "DATABASE_URL" not in serialized
    assert "REDIS_URL" not in serialized
    assert "OBJECT_STORAGE_SECRET_KEY" not in serialized


def test_provider_metadata_reports_active_default_providers() -> None:
    metadata = ProviderRegistry(ProviderSettings()).ready_metadata()

    assert metadata["tier"] == "free"
    assert metadata["live_ocr_enabled"] is False
    assert metadata["ocr_cache_enabled"] is True
    assert metadata["active"]["ocr"]["name"] == "mock"
    assert metadata["active"]["ocr"]["adapter"] == "MockOCRProvider"
    assert metadata["active"]["extraction"]["name"] == "rule_based_insurance"
    assert metadata["active"]["extraction"]["adapter"] == "RuleBasedInsuranceExtractionProvider"


def test_provider_metadata_reports_local_pdf_text_as_free_and_non_live() -> None:
    metadata = ProviderRegistry(ProviderSettings(ocr_provider="local_pdf_text")).ready_metadata()
    ocr = metadata["active"]["ocr"]

    assert ocr["name"] == "local_pdf_text"
    assert ocr["adapter"] == "LocalPDFTextOCRProvider"
    assert ocr["paid"] is False
    assert ocr["live_enabled"] is False
    assert ocr["implemented"] is True


def test_provider_scorecard_blank_is_not_default_approved() -> None:
    scorecard = blank_provider_scorecard("candidate", ProviderKind.OCR)

    assert scorecard.weighted_score() == 0.0
    assert scorecard.passes_default_gate() is False


def embedded_text_pdf(text: str) -> bytes:
    return f"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 64 >>
stream
BT /F1 12 Tf 72 720 Td ({text}) Tj ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
trailer << /Root 1 0 R >>
%%EOF
""".encode("latin-1")

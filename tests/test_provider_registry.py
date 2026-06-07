import json

import pytest

from packages.providers.neurodocops_providers import (
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


def test_provider_scorecard_blank_is_not_default_approved() -> None:
    scorecard = blank_provider_scorecard("candidate", ProviderKind.OCR)

    assert scorecard.weighted_score() == 0.0
    assert scorecard.passes_default_gate() is False

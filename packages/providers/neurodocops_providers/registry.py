from __future__ import annotations

import os
from enum import Enum
from typing import Mapping

from pydantic import BaseModel, Field

from .insurance import (
    ExtractionProvider,
    MockOCRProvider,
    OCRProvider,
    RuleBasedInsuranceExtractionProvider,
)


class ProviderConfigError(RuntimeError):
    """Raised when provider configuration is unsafe or unsupported."""


class ProviderTier(str, Enum):
    FREE = "free"
    CHEAP = "cheap"
    BALANCED = "balanced"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class ProviderKind(str, Enum):
    OCR = "ocr"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    SEARCH = "search"
    AUTH = "auth"
    TELEMETRY = "telemetry"
    SECRETS = "secrets"


class ProviderSettings(BaseModel):
    ocr_provider: str = Field(default="mock", min_length=1)
    extraction_provider: str = Field(default="rule_based_insurance", min_length=1)
    reasoning_provider: str = Field(default="none", min_length=1)
    search_provider: str = Field(default="none", min_length=1)
    auth_provider: str = Field(default="dev", min_length=1)
    telemetry_provider: str = Field(default="local", min_length=1)
    secret_provider: str = Field(default="env", min_length=1)
    provider_tier: ProviderTier = ProviderTier.FREE
    live_ocr_enabled: bool = False
    max_live_ocr_pages: int = Field(default=0, ge=0)
    ocr_cache_enabled: bool = True


class ProviderSelection(BaseModel):
    kind: ProviderKind
    name: str
    tier: ProviderTier
    paid: bool
    live_enabled: bool
    implemented: bool
    adapter: str | None = None


_IMPLEMENTED_OCR = {
    "mock": "MockOCRProvider",
    "mock-ocr": "MockOCRProvider",
}

_IMPLEMENTED_EXTRACTION = {
    "rule_based_insurance": "RuleBasedInsuranceExtractionProvider",
    "rule-based-insurance": "RuleBasedInsuranceExtractionProvider",
    "rule-based-insurance-v0": "RuleBasedInsuranceExtractionProvider",
}

_KNOWN_OCR = {
    *_IMPLEMENTED_OCR,
    "local",
    "local_pdf_text",
    "paddle",
    "paddleocr",
    "surya",
    "tesseract",
    "azure",
    "azure-document-intelligence",
    "aws",
    "aws-textract",
    "google",
    "google-document-ai",
    "llamaparse",
    "abbyy",
}

_PAID_OCR = {
    "azure",
    "azure-document-intelligence",
    "aws",
    "aws-textract",
    "google",
    "google-document-ai",
    "llamaparse",
    "abbyy",
}

_KNOWN_EXTRACTION = {
    *_IMPLEMENTED_EXTRACTION,
    "llm_structured",
    "llm-structured",
    "llm-structured-extraction",
}

_KNOWN_OPTIONAL = {
    ProviderKind.REASONING: {"none", "openai", "anthropic", "gemini", "azure_openai"},
    ProviderKind.SEARCH: {"none", "postgres", "opensearch", "elasticsearch", "meilisearch"},
    ProviderKind.AUTH: {"dev", "auth0", "keycloak", "cognito", "entra"},
    ProviderKind.TELEMETRY: {"local", "none", "sentry", "datadog", "opentelemetry"},
    ProviderKind.SECRETS: {"env", "doppler", "aws_secrets_manager", "azure_key_vault", "gcp_secret_manager"},
}

_PAID_OPTIONAL = {
    ProviderKind.REASONING: {"openai", "anthropic", "gemini", "azure_openai"},
    ProviderKind.SEARCH: {"opensearch", "elasticsearch", "meilisearch"},
    ProviderKind.AUTH: {"auth0", "keycloak", "cognito", "entra"},
    ProviderKind.TELEMETRY: {"sentry", "datadog", "opentelemetry"},
    ProviderKind.SECRETS: {"doppler", "aws_secrets_manager", "azure_key_vault", "gcp_secret_manager"},
}


class ProviderRegistry:
    """Environment-driven registry for currently selectable providers.

    The registry is intentionally conservative: it can recognize future provider
    names, but only current free/local adapters can be instantiated.
    """

    def __init__(self, settings: ProviderSettings | None = None) -> None:
        self.settings = settings or load_provider_settings()
        self._validate_optional_provider_names()

    def create_ocr_provider(self) -> OCRProvider:
        name = _normalize(self.settings.ocr_provider)
        self._validate_ocr(name)
        if name in _IMPLEMENTED_OCR:
            return MockOCRProvider()
        raise ProviderConfigError(f"OCR provider '{name}' is registered but no adapter is implemented yet.")

    def create_extraction_provider(self) -> ExtractionProvider:
        name = _normalize(self.settings.extraction_provider)
        self._validate_extraction(name)
        if name in _IMPLEMENTED_EXTRACTION:
            return RuleBasedInsuranceExtractionProvider()
        raise ProviderConfigError(f"Extraction provider '{name}' is registered but no adapter is implemented yet.")

    def active_provider_payload(self) -> list[dict[str, object]]:
        return [selection.model_dump(mode="json") for selection in self.active_providers()]

    def ready_metadata(self) -> dict[str, object]:
        return {
            "tier": self.settings.provider_tier.value,
            "live_ocr_enabled": self.settings.live_ocr_enabled,
            "ocr_cache_enabled": self.settings.ocr_cache_enabled,
            "budgets": {"max_live_ocr_pages": self.settings.max_live_ocr_pages},
            "active": {
                selection.kind.value: selection.model_dump(mode="json")
                for selection in self.active_providers()
            },
        }

    def active_providers(self) -> list[ProviderSelection]:
        return [
            self._selection(ProviderKind.OCR, _normalize(self.settings.ocr_provider)),
            self._selection(ProviderKind.EXTRACTION, _normalize(self.settings.extraction_provider)),
            self._selection(ProviderKind.REASONING, _normalize(self.settings.reasoning_provider)),
            self._selection(ProviderKind.SEARCH, _normalize(self.settings.search_provider)),
            self._selection(ProviderKind.AUTH, _normalize(self.settings.auth_provider)),
            self._selection(ProviderKind.TELEMETRY, _normalize(self.settings.telemetry_provider)),
            self._selection(ProviderKind.SECRETS, _normalize(self.settings.secret_provider)),
        ]

    def _selection(self, kind: ProviderKind, name: str) -> ProviderSelection:
        if kind not in {ProviderKind.OCR, ProviderKind.EXTRACTION} and name not in _KNOWN_OPTIONAL[kind]:
            raise _unsupported(f"NEURODOCOPS_{kind.value.upper()}_PROVIDER", name, _KNOWN_OPTIONAL[kind])
        adapter = _adapter_for(kind, name)
        paid = _is_paid(kind, name)
        return ProviderSelection(
            kind=kind,
            name=name,
            tier=self.settings.provider_tier,
            paid=paid,
            live_enabled=self.settings.live_ocr_enabled if kind == ProviderKind.OCR else False,
            implemented=adapter is not None or name in {"none", "dev", "local", "env", "postgres"},
            adapter=adapter,
        )

    def _validate_ocr(self, name: str) -> None:
        if name not in _KNOWN_OCR:
            raise _unsupported("NEURODOCOPS_OCR_PROVIDER", name, _KNOWN_OCR)
        if name in _PAID_OCR:
            self._require_live_ocr(name)

    def _validate_extraction(self, name: str) -> None:
        if name == "none":
            raise ProviderConfigError("NEURODOCOPS_EXTRACTION_PROVIDER cannot be none for claim packet processing.")
        if name not in _KNOWN_EXTRACTION:
            raise _unsupported("NEURODOCOPS_EXTRACTION_PROVIDER", name, _KNOWN_EXTRACTION)

    def _validate_optional_provider_names(self) -> None:
        optional = {
            ProviderKind.REASONING: _normalize(self.settings.reasoning_provider),
            ProviderKind.SEARCH: _normalize(self.settings.search_provider),
            ProviderKind.AUTH: _normalize(self.settings.auth_provider),
            ProviderKind.TELEMETRY: _normalize(self.settings.telemetry_provider),
            ProviderKind.SECRETS: _normalize(self.settings.secret_provider),
        }
        for kind, name in optional.items():
            if name not in _KNOWN_OPTIONAL[kind]:
                raise _unsupported(f"NEURODOCOPS_{kind.value.upper()}_PROVIDER", name, _KNOWN_OPTIONAL[kind])

    def _require_live_ocr(self, provider: str) -> None:
        if not self.settings.live_ocr_enabled:
            raise ProviderConfigError(f"OCR provider '{provider}' requires NEURODOCOPS_LIVE_OCR_ENABLED=true.")
        if self.settings.max_live_ocr_pages <= 0:
            raise ProviderConfigError(f"OCR provider '{provider}' requires NEURODOCOPS_MAX_LIVE_OCR_PAGES > 0.")


def load_provider_settings(environ: Mapping[str, str] | None = None) -> ProviderSettings:
    env = environ if environ is not None else os.environ
    return ProviderSettings(
        ocr_provider=_env_text(env, "NEURODOCOPS_OCR_PROVIDER", "mock"),
        extraction_provider=_env_text(env, "NEURODOCOPS_EXTRACTION_PROVIDER", "rule_based_insurance"),
        reasoning_provider=_env_text(env, "NEURODOCOPS_REASONING_PROVIDER", "none"),
        search_provider=_env_text(env, "NEURODOCOPS_SEARCH_PROVIDER", "none"),
        auth_provider=_env_text(env, "NEURODOCOPS_AUTH_PROVIDER", "dev"),
        telemetry_provider=_env_text(env, "NEURODOCOPS_TELEMETRY_PROVIDER", "local"),
        secret_provider=_env_text(env, "NEURODOCOPS_SECRET_PROVIDER", "env"),
        provider_tier=_env_tier(env, "NEURODOCOPS_PROVIDER_TIER", ProviderTier.FREE),
        live_ocr_enabled=_env_bool(env, "NEURODOCOPS_LIVE_OCR_ENABLED", False),
        max_live_ocr_pages=_env_int(env, "NEURODOCOPS_MAX_LIVE_OCR_PAGES", 0),
        ocr_cache_enabled=_env_bool(env, "NEURODOCOPS_OCR_CACHE_ENABLED", True),
    )


def create_provider_registry(settings: ProviderSettings | None = None) -> ProviderRegistry:
    return ProviderRegistry(settings=settings)


def create_ocr_provider(settings: ProviderSettings | None = None) -> OCRProvider:
    return create_provider_registry(settings).create_ocr_provider()


def create_extraction_provider(settings: ProviderSettings | None = None) -> ExtractionProvider:
    return create_provider_registry(settings).create_extraction_provider()


def get_provider_metadata(settings: ProviderSettings | None = None) -> dict[str, object]:
    return create_provider_registry(settings).ready_metadata()


def _adapter_for(kind: ProviderKind, name: str) -> str | None:
    if kind == ProviderKind.OCR:
        return _IMPLEMENTED_OCR.get(name)
    if kind == ProviderKind.EXTRACTION:
        return _IMPLEMENTED_EXTRACTION.get(name)
    return None


def _is_paid(kind: ProviderKind, name: str) -> bool:
    if kind == ProviderKind.OCR:
        return name in _PAID_OCR
    return name in _PAID_OPTIONAL.get(kind, set())


def _env_text(env: Mapping[str, str], name: str, default: str) -> str:
    return _normalize(env.get(name) or default)


def _normalize(value: str) -> str:
    return value.strip().lower()


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ProviderConfigError(f"{name} must be a boolean value, got: {raw}")


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ProviderConfigError(f"{name} must be a non-negative integer, got: {raw}") from exc
    if value < 0:
        raise ProviderConfigError(f"{name} must be a non-negative integer, got: {raw}")
    return value


def _env_tier(env: Mapping[str, str], name: str, default: ProviderTier) -> ProviderTier:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    try:
        return ProviderTier(normalized)
    except ValueError as exc:
        valid = ", ".join(tier.value for tier in ProviderTier)
        raise ProviderConfigError(f"Unsupported {name}: {normalized}. Supported values: {valid}") from exc


def _unsupported(env_name: str, value: str, supported: set[str]) -> ProviderConfigError:
    return ProviderConfigError(f"Unsupported {env_name}: {value}. Supported values: {', '.join(sorted(supported))}")

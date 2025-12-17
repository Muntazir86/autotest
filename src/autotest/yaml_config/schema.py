"""Pydantic models for YAML configuration schema.

This module defines the complete configuration structure for the YAML config system.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AuthType(str, Enum):
    """Authentication method types."""

    BEARER = "bearer"
    OAUTH2 = "oauth2"
    BASIC = "basic"
    API_KEY = "api_key"
    CUSTOM = "custom"


class OAuth2Flow(str, Enum):
    """OAuth2 flow types."""

    CLIENT_CREDENTIALS = "client_credentials"
    PASSWORD = "password"
    AUTHORIZATION_CODE = "authorization_code"


class GenerationMode(str, Enum):
    """Test generation modes."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    ALL = "all"


class TestPhase(str, Enum):
    """Test execution phases."""

    EXAMPLES = "examples"
    COVERAGE = "coverage"
    FUZZING = "fuzzing"
    STATEFUL = "stateful"


class ConsoleStyle(str, Enum):
    """Console output styles."""

    SIMPLE = "simple"
    RICH = "rich"
    QUIET = "quiet"


class BackoffType(str, Enum):
    """Retry backoff types."""

    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class ApiSpecConfig(BaseModel):
    """API specification source configuration."""

    type: Literal["url", "file"] = "file"
    path: str

    model_config = {"extra": "forbid"}


class ApiConfig(BaseModel):
    """API configuration section."""

    spec: ApiSpecConfig | None = None
    base_url: str | None = None
    name: str | None = None
    version: str | None = None

    model_config = {"extra": "forbid"}


class BearerAuthConfig(BaseModel):
    """Bearer token authentication configuration."""

    type: Literal["bearer"] = "bearer"
    token: str | None = None
    token_file: str | None = None

    model_config = {"extra": "forbid"}


class OAuth2AuthConfig(BaseModel):
    """OAuth2 authentication configuration."""

    type: Literal["oauth2"] = "oauth2"
    flow: OAuth2Flow = OAuth2Flow.CLIENT_CREDENTIALS
    token_url: str
    client_id: str
    client_secret: str
    scopes: list[str] = Field(default_factory=list)
    refresh_buffer_seconds: int = 60

    model_config = {"extra": "forbid"}


class BasicAuthConfig(BaseModel):
    """HTTP Basic authentication configuration."""

    type: Literal["basic"] = "basic"
    username: str
    password: str

    model_config = {"extra": "forbid"}


class ApiKeyAuthConfig(BaseModel):
    """API Key authentication configuration."""

    type: Literal["api_key"] = "api_key"
    key: str
    header: str = "X-API-Key"
    location: Literal["header", "query"] = "header"

    model_config = {"extra": "forbid"}


class CustomAuthConfig(BaseModel):
    """Custom authentication configuration."""

    type: Literal["custom"] = "custom"
    hook: str

    model_config = {"extra": "forbid"}


AuthMethodConfig = BearerAuthConfig | OAuth2AuthConfig | BasicAuthConfig | ApiKeyAuthConfig | CustomAuthConfig


class EndpointAuthConfig(BaseModel):
    """Endpoint-specific authentication configuration."""

    pattern: str
    method: str | None = None
    scopes: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class AuthConfig(BaseModel):
    """Authentication configuration section."""

    default: str | None = None
    methods: dict[str, AuthMethodConfig] = Field(default_factory=dict)
    endpoints: list[EndpointAuthConfig] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = False
    requests_per_second: float = 10.0
    burst: int = 20

    model_config = {"extra": "forbid"}


class BackoffConfig(BaseModel):
    """Retry backoff configuration."""

    type: BackoffType = BackoffType.EXPONENTIAL
    initial: float = 1.0
    max: float = 30.0

    model_config = {"extra": "forbid"}


class RetryConfig(BaseModel):
    """Retry configuration."""

    enabled: bool = True
    max_attempts: int = 3
    backoff: BackoffConfig = Field(default_factory=BackoffConfig)
    retry_on: list[int] = Field(default_factory=lambda: [429, 503, 504])

    model_config = {"extra": "forbid"}


class ClientCertConfig(BaseModel):
    """Client certificate configuration for mTLS."""

    cert: str
    key: str

    model_config = {"extra": "forbid"}


class ProxyConfig(BaseModel):
    """Proxy configuration."""

    http: str | None = None
    https: str | None = None

    model_config = {"extra": "forbid"}


class RequestConfig(BaseModel):
    """Request configuration section."""

    timeout: float = 30.0
    headers: dict[str, str] = Field(default_factory=dict)
    follow_redirects: bool = True
    max_redirects: int = 5
    verify_ssl: bool = True
    ca_bundle: str | None = None
    client_cert: ClientCertConfig | None = None
    proxy: ProxyConfig | None = None
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    model_config = {"extra": "forbid"}


class GenerationConfig(BaseModel):
    """Test generation configuration section."""

    max_examples: int = 100
    mode: GenerationMode = GenerationMode.ALL
    phases: list[TestPhase] = Field(
        default_factory=lambda: [TestPhase.EXAMPLES, TestPhase.COVERAGE, TestPhase.FUZZING, TestPhase.STATEFUL]
    )
    deterministic: bool = False
    seed: int | None = None
    shrinking: bool = True
    unique: bool = True

    model_config = {"extra": "forbid"}


class SchemaValidationConfig(BaseModel):
    """Schema validation settings."""

    strict: bool = False
    ignore_errors: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ValidationConfig(BaseModel):
    """Validation and checks configuration section."""

    checks: list[str] = Field(
        default_factory=lambda: [
            "not_a_server_error",
            "status_code_conformance",
            "content_type_conformance",
            "response_schema_conformance",
        ]
    )
    custom_checks: list[str] = Field(default_factory=list)
    schema_validation: SchemaValidationConfig = Field(default_factory=SchemaValidationConfig, alias="schema")

    model_config = {"extra": "forbid", "populate_by_name": True}


class IDExtractionConfig(BaseModel):
    """ID extraction configuration section."""

    enabled: bool = True
    strategies: list[str] = Field(
        default_factory=lambda: [
            "path_parameter_matching",
            "common_id_fields",
            "schema_hints",
            "response_headers",
            "openapi_links",
        ]
    )
    patterns: list[str] = Field(default_factory=lambda: ["id", "*_id", "*Id", "uuid", "*_uuid"])
    mappings: dict[str, dict[str, Any]] = Field(default_factory=dict)
    injection: dict[str, Any] = Field(default_factory=lambda: {"prefer": "latest", "fallback_to_generated": True})
    persistence: dict[str, Any] = Field(default_factory=lambda: {"enabled": False, "path": "./.id-store.json"})

    model_config = {"extra": "forbid"}


class WorkflowSettingsConfig(BaseModel):
    """Workflow execution settings."""

    parallel: bool = False
    max_parallel: int = 4
    timeout: int = 600
    fail_fast: bool = False
    cleanup_on_failure: bool = True

    model_config = {"extra": "forbid"}


class WorkflowsConfig(BaseModel):
    """Workflows configuration section."""

    directory: str = "./workflows"
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    settings: WorkflowSettingsConfig = Field(default_factory=WorkflowSettingsConfig)

    model_config = {"extra": "forbid"}


class EndpointOverrideSettings(BaseModel):
    """Settings for endpoint-specific overrides."""

    max_examples: int | None = None
    timeout: float | None = None
    rate_limit: RateLimitConfig | None = None

    model_config = {"extra": "forbid"}


class EndpointOverride(BaseModel):
    """Endpoint-specific override configuration."""

    pattern: str
    settings: EndpointOverrideSettings

    model_config = {"extra": "forbid"}


class EndpointsConfig(BaseModel):
    """Endpoint filtering configuration section."""

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    include_tags: list[str] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    include_operations: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE"])
    overrides: list[EndpointOverride] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class ExecutionConfig(BaseModel):
    """Execution configuration section."""

    workers: str | int = "auto"
    timeout: int = 3600
    fail_fast: bool = False
    verbose: bool = False
    dry_run: bool = False

    model_config = {"extra": "forbid"}

    @field_validator("workers", mode="before")
    @classmethod
    def validate_workers(cls, v: Any) -> str | int:
        if isinstance(v, str) and v != "auto":
            try:
                return int(v)
            except ValueError:
                raise ValueError("workers must be 'auto' or an integer")
        return v


class HTMLReportConfig(BaseModel):
    """HTML report configuration."""

    enabled: bool = True
    path: str = "${output_dir}/report.html"
    title: str | None = None
    include_passed_details: bool = False
    max_body_size: int = 10240
    sanitize_headers: list[str] = Field(default_factory=lambda: ["Authorization", "X-API-Key", "Cookie"])

    model_config = {"extra": "forbid"}


class JUnitReportConfig(BaseModel):
    """JUnit XML report configuration."""

    enabled: bool = False
    path: str = "${output_dir}/junit.xml"

    model_config = {"extra": "forbid"}


class JSONReportConfig(BaseModel):
    """JSON report configuration."""

    enabled: bool = False
    path: str = "${output_dir}/report.json"
    pretty: bool = True

    model_config = {"extra": "forbid"}


class VCRReportConfig(BaseModel):
    """VCR cassette report configuration."""

    enabled: bool = False
    path: str = "${output_dir}/cassette.yaml"

    model_config = {"extra": "forbid"}


class HARReportConfig(BaseModel):
    """HAR file report configuration."""

    enabled: bool = False
    path: str = "${output_dir}/requests.har"

    model_config = {"extra": "forbid"}


class ConsoleConfig(BaseModel):
    """Console output configuration."""

    style: ConsoleStyle = ConsoleStyle.RICH
    show_failures: bool = True
    color: bool = True

    model_config = {"extra": "forbid"}


class ReportingConfig(BaseModel):
    """Reporting configuration section."""

    output_dir: str = "./reports"
    html: HTMLReportConfig = Field(default_factory=HTMLReportConfig)
    junit: JUnitReportConfig = Field(default_factory=JUnitReportConfig)
    json_report: JSONReportConfig = Field(default_factory=JSONReportConfig, alias="json")
    vcr: VCRReportConfig = Field(default_factory=VCRReportConfig)
    har: HARReportConfig = Field(default_factory=HARReportConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)

    model_config = {"extra": "forbid", "populate_by_name": True}


class DataConfig(BaseModel):
    """Data generation configuration section."""

    locale: str = "en_US"
    generators: dict[str, str] = Field(default_factory=dict)
    overrides: dict[str, str] = Field(default_factory=dict)
    fixtures: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class HooksConfig(BaseModel):
    """Hooks and extensions configuration section."""

    files: list[str] = Field(default_factory=list)
    before_call: list[str] = Field(default_factory=list)
    after_call: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class EnvironmentOverride(BaseModel):
    """Environment-specific configuration override."""

    api: ApiConfig | None = None
    auth: AuthConfig | None = None
    request: RequestConfig | None = None
    generation: GenerationConfig | None = None
    validation: ValidationConfig | None = None
    endpoints: EndpointsConfig | None = None
    execution: ExecutionConfig | None = None
    reporting: ReportingConfig | None = None

    model_config = {"extra": "forbid"}


class YAMLConfig(BaseModel):
    """Complete YAML configuration model."""

    config_version: str = "1.0"
    extends: list[str] = Field(default_factory=list)
    profile: str | None = None

    api: ApiConfig = Field(default_factory=ApiConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    request: RequestConfig = Field(default_factory=RequestConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    id_extraction: IDExtractionConfig = Field(default_factory=IDExtractionConfig)
    workflows: WorkflowsConfig = Field(default_factory=WorkflowsConfig)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    hooks: HooksConfig = Field(default_factory=HooksConfig)

    environments: dict[str, EnvironmentOverride] = Field(default_factory=dict)
    environment: str = "development"

    variables: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def get_effective_config(self, env: str | None = None) -> YAMLConfig:
        """Get configuration with environment overrides applied.

        Args:
            env: Environment name to apply. If None, uses self.environment.

        Returns:
            New YAMLConfig with environment overrides merged.
        """
        target_env = env or self.environment
        if target_env not in self.environments:
            return self

        override = self.environments[target_env]
        data = self.model_dump()

        # Apply overrides
        if override.api:
            data["api"] = _deep_merge(data.get("api", {}), override.api.model_dump(exclude_none=True))
        if override.auth:
            data["auth"] = _deep_merge(data.get("auth", {}), override.auth.model_dump(exclude_none=True))
        if override.request:
            data["request"] = _deep_merge(data.get("request", {}), override.request.model_dump(exclude_none=True))
        if override.generation:
            data["generation"] = _deep_merge(
                data.get("generation", {}), override.generation.model_dump(exclude_none=True)
            )
        if override.validation:
            data["validation"] = _deep_merge(
                data.get("validation", {}), override.validation.model_dump(exclude_none=True)
            )
        if override.endpoints:
            data["endpoints"] = _deep_merge(
                data.get("endpoints", {}), override.endpoints.model_dump(exclude_none=True)
            )
        if override.execution:
            data["execution"] = _deep_merge(
                data.get("execution", {}), override.execution.model_dump(exclude_none=True)
            )
        if override.reporting:
            data["reporting"] = _deep_merge(
                data.get("reporting", {}), override.reporting.model_dump(exclude_none=True)
            )

        return YAMLConfig.model_validate(data)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

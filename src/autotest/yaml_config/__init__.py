"""YAML Configuration System for Autotest.

This module provides:
- Unified YAML configuration file support
- Environment-specific overrides
- Configuration inheritance and composition
- Environment variable substitution
- Integration with CLI
"""

from __future__ import annotations

from autotest.yaml_config.schema import (
    YAMLConfig,
    ApiConfig,
    ApiSpecConfig,
    AuthConfig,
    AuthMethodConfig,
    BearerAuthConfig,
    OAuth2AuthConfig,
    BasicAuthConfig,
    ApiKeyAuthConfig,
    CustomAuthConfig,
    EndpointAuthConfig,
    RequestConfig,
    RateLimitConfig,
    RetryConfig,
    GenerationConfig,
    ValidationConfig,
    WorkflowsConfig,
    EndpointsConfig,
    EndpointOverride,
    ExecutionConfig,
    ReportingConfig,
    HTMLReportConfig,
    JUnitReportConfig,
    JSONReportConfig,
    ConsoleConfig,
    DataConfig,
    HooksConfig,
    EnvironmentOverride,
)
from autotest.yaml_config.loader import ConfigLoader
from autotest.yaml_config.resolver import VariableResolver
from autotest.yaml_config.merger import ConfigMerger
from autotest.yaml_config.validator import ConfigValidator
from autotest.yaml_config.errors import (
    YAMLConfigError,
    ConfigValidationError,
    ConfigLoadError,
    CircularInheritanceError,
    VariableResolutionError,
)
from autotest.yaml_config.templates import get_template as get_config_template, list_templates as list_config_templates

__all__ = [
    # Main config class
    "YAMLConfig",
    # Config sections
    "ApiConfig",
    "ApiSpecConfig",
    "AuthConfig",
    "AuthMethodConfig",
    "BearerAuthConfig",
    "OAuth2AuthConfig",
    "BasicAuthConfig",
    "ApiKeyAuthConfig",
    "CustomAuthConfig",
    "EndpointAuthConfig",
    "RequestConfig",
    "RateLimitConfig",
    "RetryConfig",
    "GenerationConfig",
    "ValidationConfig",
    "WorkflowsConfig",
    "EndpointsConfig",
    "EndpointOverride",
    "ExecutionConfig",
    "ReportingConfig",
    "HTMLReportConfig",
    "JUnitReportConfig",
    "JSONReportConfig",
    "ConsoleConfig",
    "DataConfig",
    "HooksConfig",
    "EnvironmentOverride",
    # Utilities
    "ConfigLoader",
    "VariableResolver",
    "ConfigMerger",
    "ConfigValidator",
    # Errors
    "YAMLConfigError",
    "ConfigValidationError",
    "ConfigLoadError",
    "CircularInheritanceError",
    "VariableResolutionError",
    # Templates
    "get_config_template",
    "list_config_templates",
]

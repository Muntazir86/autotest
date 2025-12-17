"""Configuration validator for YAML configuration.

Validates configuration structure and values beyond Pydantic's built-in validation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from autotest.yaml_config.errors import ConfigValidationError


class ConfigValidator:
    """Validates YAML configuration beyond schema validation."""

    def __init__(self, base_path: Path | None = None) -> None:
        """Initialize the validator.

        Args:
            base_path: Base path for resolving relative file paths.
        """
        self.base_path = base_path or Path.cwd()
        self.errors: list[ConfigValidationError] = []
        self.warnings: list[str] = []

    def validate(self, config: dict[str, Any], config_path: str | None = None) -> list[ConfigValidationError]:
        """Validate a configuration dictionary.

        Args:
            config: The configuration dictionary to validate.
            config_path: Path to the configuration file for error reporting.

        Returns:
            List of validation errors found.
        """
        self.errors = []
        self.warnings = []

        self._validate_api_config(config.get("api", {}), config_path)
        self._validate_auth_config(config.get("auth", {}), config_path)
        self._validate_request_config(config.get("request", {}), config_path)
        self._validate_generation_config(config.get("generation", {}), config_path)
        self._validate_validation_config(config.get("validation", {}), config_path)
        self._validate_workflows_config(config.get("workflows", {}), config_path)
        self._validate_endpoints_config(config.get("endpoints", {}), config_path)
        self._validate_reporting_config(config.get("reporting", {}), config_path)
        self._validate_environments(config.get("environments", {}), config_path)
        self._validate_extends(config.get("extends", []), config_path)

        return self.errors

    def _validate_api_config(self, api: dict[str, Any], config_path: str | None) -> None:
        """Validate API configuration section."""
        spec = api.get("spec", {})
        if spec:
            spec_type = spec.get("type", "file")
            spec_path = spec.get("path")

            if spec_path:
                # Skip validation if path contains variables
                if not self._contains_variable(spec_path):
                    if spec_type == "file":
                        resolved_path = self._resolve_path(spec_path)
                        if not resolved_path.exists():
                            self.warnings.append(f"API spec file not found: {spec_path}")
                    elif spec_type == "url":
                        if not self._is_valid_url(spec_path):
                            self.errors.append(
                                ConfigValidationError(
                                    "Invalid URL format",
                                    config_path,
                                    "api.spec.path",
                                    spec_path,
                                )
                            )

        base_url = api.get("base_url")
        if base_url and not self._contains_variable(base_url):
            if not self._is_valid_url(base_url):
                self.errors.append(
                    ConfigValidationError(
                        "Invalid URL format",
                        config_path,
                        "api.base_url",
                        base_url,
                    )
                )

    def _validate_auth_config(self, auth: dict[str, Any], config_path: str | None) -> None:
        """Validate authentication configuration section."""
        default_method = auth.get("default")
        methods = auth.get("methods", {})

        if default_method and default_method not in methods:
            self.errors.append(
                ConfigValidationError(
                    f"Default auth method '{default_method}' not defined in methods",
                    config_path,
                    "auth.default",
                    default_method,
                )
            )

        # Validate endpoint auth patterns
        for i, endpoint_auth in enumerate(auth.get("endpoints", [])):
            pattern = endpoint_auth.get("pattern")
            if pattern:
                try:
                    self._validate_glob_pattern(pattern)
                except ValueError as e:
                    self.errors.append(
                        ConfigValidationError(
                            str(e),
                            config_path,
                            f"auth.endpoints[{i}].pattern",
                            pattern,
                        )
                    )

            method = endpoint_auth.get("method")
            if method and method not in methods:
                self.errors.append(
                    ConfigValidationError(
                        f"Auth method '{method}' not defined in methods",
                        config_path,
                        f"auth.endpoints[{i}].method",
                        method,
                    )
                )

    def _validate_request_config(self, request: dict[str, Any], config_path: str | None) -> None:
        """Validate request configuration section."""
        timeout = request.get("timeout")
        if timeout is not None and timeout <= 0:
            self.errors.append(
                ConfigValidationError(
                    "Timeout must be positive",
                    config_path,
                    "request.timeout",
                    timeout,
                )
            )

        rate_limit = request.get("rate_limit", {})
        if rate_limit.get("enabled"):
            rps = rate_limit.get("requests_per_second", 10)
            if rps <= 0:
                self.errors.append(
                    ConfigValidationError(
                        "Rate limit requests_per_second must be positive",
                        config_path,
                        "request.rate_limit.requests_per_second",
                        rps,
                    )
                )

    def _validate_generation_config(self, generation: dict[str, Any], config_path: str | None) -> None:
        """Validate generation configuration section."""
        max_examples = generation.get("max_examples")
        if max_examples is not None and max_examples <= 0:
            self.errors.append(
                ConfigValidationError(
                    "max_examples must be positive",
                    config_path,
                    "generation.max_examples",
                    max_examples,
                )
            )

        valid_modes = {"positive", "negative", "all"}
        mode = generation.get("mode")
        if mode and mode not in valid_modes:
            self.errors.append(
                ConfigValidationError(
                    f"Invalid mode, must be one of: {', '.join(valid_modes)}",
                    config_path,
                    "generation.mode",
                    mode,
                )
            )

        valid_phases = {"examples", "coverage", "fuzzing", "stateful"}
        for i, phase in enumerate(generation.get("phases", [])):
            if phase not in valid_phases:
                self.errors.append(
                    ConfigValidationError(
                        f"Invalid phase, must be one of: {', '.join(valid_phases)}",
                        config_path,
                        f"generation.phases[{i}]",
                        phase,
                    )
                )

    def _validate_validation_config(self, validation: dict[str, Any], config_path: str | None) -> None:
        """Validate validation configuration section."""
        valid_checks = {
            "not_a_server_error",
            "status_code_conformance",
            "content_type_conformance",
            "response_schema_conformance",
            "response_headers_conformance",
            "negative_data_rejection",
            "positive_data_acceptance",
            "use_after_free",
            "ensure_resource_availability",
            "ignored_auth",
            "max_response_time",
            "missing_required_header",
            "unsupported_method",
        }

        for i, check in enumerate(validation.get("checks", [])):
            if check not in valid_checks:
                self.warnings.append(f"Unknown check '{check}' at validation.checks[{i}]")

        # Validate custom check files exist
        for i, check_file in enumerate(validation.get("custom_checks", [])):
            if not self._contains_variable(check_file):
                resolved_path = self._resolve_path(check_file)
                if not resolved_path.exists():
                    self.warnings.append(f"Custom check file not found: {check_file}")

    def _validate_workflows_config(self, workflows: dict[str, Any], config_path: str | None) -> None:
        """Validate workflows configuration section."""
        directory = workflows.get("directory")
        if directory and not self._contains_variable(directory):
            resolved_path = self._resolve_path(directory)
            if not resolved_path.exists():
                self.warnings.append(f"Workflows directory not found: {directory}")

        settings = workflows.get("settings", {})
        timeout = settings.get("timeout")
        if timeout is not None and timeout <= 0:
            self.errors.append(
                ConfigValidationError(
                    "Workflow timeout must be positive",
                    config_path,
                    "workflows.settings.timeout",
                    timeout,
                )
            )

    def _validate_endpoints_config(self, endpoints: dict[str, Any], config_path: str | None) -> None:
        """Validate endpoints configuration section."""
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

        for i, method in enumerate(endpoints.get("methods", [])):
            if method.upper() not in valid_methods:
                self.errors.append(
                    ConfigValidationError(
                        f"Invalid HTTP method, must be one of: {', '.join(valid_methods)}",
                        config_path,
                        f"endpoints.methods[{i}]",
                        method,
                    )
                )

        # Validate patterns
        for i, pattern in enumerate(endpoints.get("include", [])):
            try:
                self._validate_glob_pattern(pattern)
            except ValueError as e:
                self.errors.append(
                    ConfigValidationError(
                        str(e),
                        config_path,
                        f"endpoints.include[{i}]",
                        pattern,
                    )
                )

        for i, pattern in enumerate(endpoints.get("exclude", [])):
            try:
                self._validate_glob_pattern(pattern)
            except ValueError as e:
                self.errors.append(
                    ConfigValidationError(
                        str(e),
                        config_path,
                        f"endpoints.exclude[{i}]",
                        pattern,
                    )
                )

    def _validate_reporting_config(self, reporting: dict[str, Any], config_path: str | None) -> None:
        """Validate reporting configuration section."""
        html = reporting.get("html", {})
        max_body_size = html.get("max_body_size")
        if max_body_size is not None and max_body_size < 0:
            self.errors.append(
                ConfigValidationError(
                    "max_body_size cannot be negative",
                    config_path,
                    "reporting.html.max_body_size",
                    max_body_size,
                )
            )

    def _validate_environments(self, environments: dict[str, Any], config_path: str | None) -> None:
        """Validate environment overrides."""
        for env_name, env_config in environments.items():
            if not isinstance(env_config, dict):
                self.errors.append(
                    ConfigValidationError(
                        "Environment override must be a dictionary",
                        config_path,
                        f"environments.{env_name}",
                        type(env_config).__name__,
                    )
                )

    def _validate_extends(self, extends: list[str], config_path: str | None) -> None:
        """Validate extends paths."""
        for i, path in enumerate(extends):
            if not self._contains_variable(path):
                resolved_path = self._resolve_path(path)
                if not resolved_path.exists():
                    self.errors.append(
                        ConfigValidationError(
                            f"Extended config file not found: {path}",
                            config_path,
                            f"extends[{i}]",
                            path,
                        )
                    )

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def _contains_variable(self, value: str) -> bool:
        """Check if a string contains variable expressions."""
        return "${" in value

    def _is_valid_url(self, url: str) -> bool:
        """Check if a string is a valid URL."""
        url_pattern = re.compile(
            r"^https?://"
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
            r"localhost|"
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            r"(?::\d+)?"
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return bool(url_pattern.match(url))

    def _validate_glob_pattern(self, pattern: str) -> None:
        """Validate a glob pattern."""
        # Basic validation - just check for obviously invalid patterns
        if pattern.count("[") != pattern.count("]"):
            raise ValueError("Unbalanced brackets in pattern")
        if pattern.count("{") != pattern.count("}"):
            raise ValueError("Unbalanced braces in pattern")

    def get_warnings(self) -> list[str]:
        """Get validation warnings."""
        return self.warnings

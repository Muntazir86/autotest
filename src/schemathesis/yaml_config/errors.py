"""Error classes for YAML configuration system."""

from __future__ import annotations

from typing import Any


class YAMLConfigError(Exception):
    """Base exception for YAML configuration errors."""

    def __init__(self, message: str, path: str | None = None) -> None:
        self.message = message
        self.path = path
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.path:
            return f"{self.message} (in {self.path})"
        return self.message


class ConfigValidationError(YAMLConfigError):
    """Raised when configuration validation fails."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        field_path: str | None = None,
        value: Any = None,
    ) -> None:
        self.field_path = field_path
        self.value = value
        super().__init__(message, path)

    def _format_message(self) -> str:
        parts = []
        if self.field_path:
            parts.append(f"Field '{self.field_path}'")
        parts.append(self.message)
        if self.value is not None:
            parts.append(f"(got: {self.value!r})")
        msg = ": ".join(parts) if len(parts) > 1 else parts[0]
        if self.path:
            msg = f"{msg} (in {self.path})"
        return msg


class ConfigLoadError(YAMLConfigError):
    """Raised when configuration file cannot be loaded."""

    pass


class CircularInheritanceError(YAMLConfigError):
    """Raised when circular inheritance is detected in configuration files."""

    def __init__(self, chain: list[str]) -> None:
        self.chain = chain
        message = f"Circular inheritance detected: {' -> '.join(chain)}"
        super().__init__(message)


class VariableResolutionError(YAMLConfigError):
    """Raised when a variable cannot be resolved."""

    def __init__(
        self,
        variable: str,
        message: str | None = None,
        path: str | None = None,
    ) -> None:
        self.variable = variable
        msg = message or f"Cannot resolve variable '${{{variable}}}'"
        super().__init__(msg, path)


class MissingEnvironmentVariableError(VariableResolutionError):
    """Raised when a required environment variable is not set."""

    def __init__(self, variable: str, path: str | None = None) -> None:
        super().__init__(
            variable,
            f"Environment variable '{variable}' is not set and no default provided",
            path,
        )


class FileIncludeError(YAMLConfigError):
    """Raised when a file include fails."""

    def __init__(self, file_path: str, reason: str, config_path: str | None = None) -> None:
        self.file_path = file_path
        self.reason = reason
        message = f"Failed to include file '{file_path}': {reason}"
        super().__init__(message, config_path)

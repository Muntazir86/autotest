"""Variable resolver for YAML configuration.

Handles resolution of ${...} expressions including:
- Environment variables: ${env:VAR_NAME} or ${env:VAR_NAME:default}
- File includes: ${file:path} or ${json:path}
- Dynamic values: ${now}, ${uuid}, ${random}
- Conditional expressions: ${if:condition,then,else}
"""

from __future__ import annotations

import json
import os
import re
import uuid as uuid_module
from datetime import datetime
from pathlib import Path
from typing import Any

from schemathesis.yaml_config.errors import (
    FileIncludeError,
    MissingEnvironmentVariableError,
    VariableResolutionError,
)


class VariableResolver:
    """Resolves ${...} variable expressions in configuration values."""

    # Pattern to match ${...} expressions
    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

    # Patterns for specific variable types
    ENV_PATTERN = re.compile(r"^env:(\w+)(?::(.*))?$")
    FILE_PATTERN = re.compile(r"^file:(.+)$")
    JSON_PATTERN = re.compile(r"^json:(.+)$")
    NOW_PATTERN = re.compile(r"^now(?::format=(.+))?$")
    RANDOM_PATTERN = re.compile(r"^random(?::(.+))?$")
    IF_PATTERN = re.compile(r"^if:(.+),(.+),(.+)$")
    CONFIG_PATTERN = re.compile(r"^config:(.+)$")

    def __init__(self, base_path: Path | None = None, config_context: dict[str, Any] | None = None) -> None:
        """Initialize the resolver.

        Args:
            base_path: Base path for resolving relative file paths.
            config_context: Configuration context for ${config:...} references.
        """
        self.base_path = base_path or Path.cwd()
        self.config_context = config_context or {}
        self._resolution_stack: list[str] = []

    def resolve(self, value: Any, path: str | None = None) -> Any:
        """Resolve all variables in a value.

        Args:
            value: The value to resolve (can be string, dict, list, or primitive).
            path: Optional path for error reporting.

        Returns:
            The value with all variables resolved.
        """
        if isinstance(value, str):
            return self._resolve_string(value, path)
        elif isinstance(value, dict):
            return {k: self.resolve(v, f"{path}.{k}" if path else k) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve(item, f"{path}[{i}]" if path else f"[{i}]") for i, item in enumerate(value)]
        return value

    def _resolve_string(self, value: str, path: str | None = None) -> Any:
        """Resolve variables in a string value.

        If the entire string is a single variable expression, the resolved value
        is returned directly (preserving type). Otherwise, variable expressions
        are interpolated into the string.
        """
        # Check if the entire string is a single variable expression
        match = self.VARIABLE_PATTERN.fullmatch(value)
        if match:
            return self._resolve_expression(match.group(1), path)

        # Otherwise, interpolate all expressions into the string
        def replace_match(m: re.Match[str]) -> str:
            result = self._resolve_expression(m.group(1), path)
            return str(result) if result is not None else ""

        return self.VARIABLE_PATTERN.sub(replace_match, value)

    def _resolve_expression(self, expr: str, path: str | None = None) -> Any:
        """Resolve a single variable expression (without ${...} wrapper)."""
        # Check for circular references
        if expr in self._resolution_stack:
            raise VariableResolutionError(
                expr,
                f"Circular reference detected: {' -> '.join(self._resolution_stack)} -> {expr}",
                path,
            )

        self._resolution_stack.append(expr)
        try:
            return self._do_resolve_expression(expr, path)
        finally:
            self._resolution_stack.pop()

    def _do_resolve_expression(self, expr: str, path: str | None = None) -> Any:
        """Actually resolve the expression."""
        # Environment variable: ${env:VAR_NAME} or ${env:VAR_NAME:default}
        match = self.ENV_PATTERN.match(expr)
        if match:
            var_name = match.group(1)
            default = match.group(2)
            value = os.environ.get(var_name)
            if value is None:
                if default is not None:
                    return default
                raise MissingEnvironmentVariableError(var_name, path)
            return value

        # File include: ${file:path}
        match = self.FILE_PATTERN.match(expr)
        if match:
            file_path = match.group(1)
            return self._read_file(file_path, path)

        # JSON file include: ${json:path}
        match = self.JSON_PATTERN.match(expr)
        if match:
            file_path = match.group(1)
            return self._read_json_file(file_path, path)

        # Timestamp: ${now} or ${now:format=...}
        match = self.NOW_PATTERN.match(expr)
        if match:
            format_str = match.group(1)
            return self._generate_timestamp(format_str)

        # UUID: ${uuid}
        if expr == "uuid":
            return str(uuid_module.uuid4())

        # Random: ${random} or ${random:length=N} or ${random:min=X,max=Y}
        match = self.RANDOM_PATTERN.match(expr)
        if match:
            params = match.group(1)
            return self._generate_random(params)

        # Conditional: ${if:condition,then,else}
        match = self.IF_PATTERN.match(expr)
        if match:
            condition = match.group(1).strip()
            then_value = match.group(2).strip()
            else_value = match.group(3).strip()
            return self._evaluate_conditional(condition, then_value, else_value, path)

        # Config reference: ${config:path.to.value}
        match = self.CONFIG_PATTERN.match(expr)
        if match:
            config_path = match.group(1)
            return self._resolve_config_path(config_path, path)

        # Simple variable reference from context
        if expr in self.config_context.get("variables", {}):
            return self.config_context["variables"][expr]

        # Unknown expression - return as-is or raise error
        raise VariableResolutionError(expr, f"Unknown variable expression: ${{{expr}}}", path)

    def _read_file(self, file_path: str, config_path: str | None = None) -> str:
        """Read contents of a file."""
        resolved_path = self._resolve_file_path(file_path)
        try:
            return resolved_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            raise FileIncludeError(file_path, "File not found", config_path)
        except PermissionError:
            raise FileIncludeError(file_path, "Permission denied", config_path)
        except Exception as e:
            raise FileIncludeError(file_path, str(e), config_path)

    def _read_json_file(self, file_path: str, config_path: str | None = None) -> Any:
        """Read and parse a JSON file."""
        resolved_path = self._resolve_file_path(file_path)
        try:
            content = resolved_path.read_text(encoding="utf-8")
            return json.loads(content)
        except FileNotFoundError:
            raise FileIncludeError(file_path, "File not found", config_path)
        except json.JSONDecodeError as e:
            raise FileIncludeError(file_path, f"Invalid JSON: {e}", config_path)
        except Exception as e:
            raise FileIncludeError(file_path, str(e), config_path)

    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve a file path relative to base_path."""
        path = Path(file_path)
        if path.is_absolute():
            return path
        return self.base_path / path

    def _generate_timestamp(self, format_str: str | None = None) -> str:
        """Generate a timestamp string."""
        now = datetime.utcnow()
        if format_str is None or format_str == "ISO":
            return now.isoformat() + "Z"

        # Convert common format specifiers
        format_map = {
            "YYYY": "%Y",
            "MM": "%m",
            "DD": "%d",
            "HH": "%H",
            "mm": "%M",
            "ss": "%S",
        }
        py_format = format_str
        for token, py_token in format_map.items():
            py_format = py_format.replace(token, py_token)

        return now.strftime(py_format)

    def _generate_random(self, params: str | None = None) -> str | int:
        """Generate a random value."""
        import random
        import string

        if params is None:
            # Default: 8-character alphanumeric string
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

        # Parse parameters
        param_dict: dict[str, str] = {}
        for part in params.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                param_dict[key.strip()] = value.strip()

        if "length" in param_dict:
            length = int(param_dict["length"])
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

        if "min" in param_dict and "max" in param_dict:
            min_val = int(param_dict["min"])
            max_val = int(param_dict["max"])
            return random.randint(min_val, max_val)

        # Default behavior
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    def _evaluate_conditional(
        self, condition: str, then_value: str, else_value: str, path: str | None = None
    ) -> str:
        """Evaluate a conditional expression."""
        # Simple boolean evaluation
        condition_lower = condition.lower().strip()
        if condition_lower in ("true", "1", "yes"):
            result = True
        elif condition_lower in ("false", "0", "no", ""):
            result = False
        else:
            # Try to resolve the condition as a variable
            try:
                resolved = self._resolve_string(f"${{{condition}}}", path)
                result = bool(resolved) and str(resolved).lower() not in ("false", "0", "no", "")
            except VariableResolutionError:
                result = False

        return then_value if result else else_value

    def _resolve_config_path(self, config_path: str, error_path: str | None = None) -> Any:
        """Resolve a dotted path in the config context."""
        parts = config_path.split(".")
        current = self.config_context

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise VariableResolutionError(
                    f"config:{config_path}",
                    f"Config path '{config_path}' not found",
                    error_path,
                )

        return current

    def update_context(self, context: dict[str, Any]) -> None:
        """Update the configuration context."""
        self.config_context = context

    def set_base_path(self, base_path: Path) -> None:
        """Set the base path for file resolution."""
        self.base_path = base_path

"""Expression engine for workflow variable resolution and evaluation.

Handles ${...} expressions including:
- Variable references: ${var_name}
- JSONPath extraction: $.field.nested
- Built-in functions: ${now}, ${uuid}, ${random}, ${faker:type}
- Comparisons: ${gte:10}, ${between:0,100}
- Type checks: ${type:string}
"""

from __future__ import annotations

import json
import random
import re
import string
import uuid as uuid_module
from datetime import datetime
from typing import Any, Callable

from autotest.workflows.errors import ExpressionError


class ExpressionEngine:
    """Evaluates expressions in workflow definitions."""

    # Pattern to match ${...} expressions
    VARIABLE_PATTERN = re.compile(r"\$\{([^}]+)\}")

    # Patterns for specific expression types
    ENV_PATTERN = re.compile(r"^env:(\w+)(?::(.*))?$")
    NOW_PATTERN = re.compile(r"^now(?::format=(.+))?$")
    RANDOM_PATTERN = re.compile(r"^random(?::(.+))?$")
    FAKER_PATTERN = re.compile(r"^faker:(\w+)$")
    EXTRACT_PATTERN = re.compile(r"^extract:(\w+)$")
    TYPE_PATTERN = re.compile(r"^type:(\w+)$")
    REGEX_PATTERN = re.compile(r"^regex:(.+)$")
    GTE_PATTERN = re.compile(r"^gte:(.+)$")
    LTE_PATTERN = re.compile(r"^lte:(.+)$")
    GT_PATTERN = re.compile(r"^gt:(.+)$")
    LT_PATTERN = re.compile(r"^lt:(.+)$")
    BETWEEN_PATTERN = re.compile(r"^between:(.+),(.+)$")
    CONTAINS_PATTERN = re.compile(r"^contains:(.+)$")
    LENGTH_PATTERN = re.compile(r"^length$")
    EACH_PATTERN = re.compile(r"^each$")
    STEPS_PATTERN = re.compile(r"^steps\.(\w+)\.(.+)$")
    RESPONSE_PATTERN = re.compile(r"^response\.(.+)$")
    CONFIG_PATTERN = re.compile(r"^config:(.+)$")

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        """Initialize the expression engine.

        Args:
            context: Initial variable context.
        """
        self.context = context or {}
        self._faker = None

    def evaluate(self, value: Any, workflow_name: str | None = None, step_name: str | None = None) -> Any:
        """Evaluate all expressions in a value.

        Args:
            value: The value to evaluate (can be string, dict, list, or primitive).
            workflow_name: Workflow name for error reporting.
            step_name: Step name for error reporting.

        Returns:
            The value with all expressions evaluated.
        """
        if isinstance(value, str):
            return self._evaluate_string(value, workflow_name, step_name)
        elif isinstance(value, dict):
            return {k: self.evaluate(v, workflow_name, step_name) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.evaluate(item, workflow_name, step_name) for item in value]
        return value

    def _evaluate_string(self, value: str, workflow_name: str | None, step_name: str | None) -> Any:
        """Evaluate expressions in a string value."""
        # Check if the entire string is a single expression
        match = self.VARIABLE_PATTERN.fullmatch(value)
        if match:
            return self._evaluate_expression(match.group(1), workflow_name, step_name)

        # Otherwise, interpolate all expressions into the string
        def replace_match(m: re.Match[str]) -> str:
            result = self._evaluate_expression(m.group(1), workflow_name, step_name)
            return str(result) if result is not None else ""

        return self.VARIABLE_PATTERN.sub(replace_match, value)

    def _evaluate_expression(self, expr: str, workflow_name: str | None, step_name: str | None) -> Any:
        """Evaluate a single expression."""
        try:
            return self._do_evaluate_expression(expr)
        except ExpressionError:
            raise
        except Exception as e:
            raise ExpressionError(expr, str(e), workflow_name, step_name)

    def _do_evaluate_expression(self, expr: str) -> Any:
        """Actually evaluate the expression."""
        import os

        # Environment variable: ${env:VAR_NAME} or ${env:VAR_NAME:default}
        match = self.ENV_PATTERN.match(expr)
        if match:
            var_name = match.group(1)
            default = match.group(2)
            value = os.environ.get(var_name)
            if value is None:
                if default is not None:
                    return default
                raise ExpressionError(expr, f"Environment variable '{var_name}' not set")
            return value

        # Timestamp: ${now} or ${now:format=...}
        match = self.NOW_PATTERN.match(expr)
        if match:
            format_str = match.group(1)
            return self._generate_timestamp(format_str)

        # UUID: ${uuid}
        if expr == "uuid":
            return str(uuid_module.uuid4())

        # Timestamp shorthand
        if expr == "timestamp":
            return datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Random: ${random} or ${random:length=N} or ${random:min=X,max=Y}
        match = self.RANDOM_PATTERN.match(expr)
        if match:
            params = match.group(1)
            return self._generate_random(params)

        # Faker: ${faker:type}
        match = self.FAKER_PATTERN.match(expr)
        if match:
            faker_type = match.group(1)
            return self._generate_faker(faker_type)

        # Extract marker: ${extract:name}
        match = self.EXTRACT_PATTERN.match(expr)
        if match:
            # Return a special marker that will be handled during extraction
            return {"__extract__": match.group(1)}

        # Steps reference: ${steps.step_name.field}
        match = self.STEPS_PATTERN.match(expr)
        if match:
            step_name = match.group(1)
            field_path = match.group(2)
            return self._resolve_steps_reference(step_name, field_path)

        # Response reference: ${response.field}
        match = self.RESPONSE_PATTERN.match(expr)
        if match:
            field_path = match.group(1)
            return self._resolve_response_reference(field_path)

        # Config reference: ${config:path}
        match = self.CONFIG_PATTERN.match(expr)
        if match:
            config_path = match.group(1)
            return self._resolve_config_reference(config_path)

        # Simple variable reference
        if expr in self.context:
            return self.context[expr]

        # Check in variables sub-context
        if "variables" in self.context and expr in self.context["variables"]:
            return self.context["variables"][expr]

        # Check for dotted path in context
        if "." in expr:
            return self._resolve_dotted_path(expr, self.context)

        # Return the expression as-is if not found (might be resolved later)
        raise ExpressionError(expr, f"Variable '{expr}' not found in context")

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
        if params is None:
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

        return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

    def _generate_faker(self, faker_type: str) -> Any:
        """Generate fake data using Faker."""
        if self._faker is None:
            try:
                from faker import Faker

                self._faker = Faker()
            except ImportError:
                raise ExpressionError(
                    f"faker:{faker_type}",
                    "Faker library not installed. Install with: pip install faker",
                )

        # Map common types to Faker methods
        faker_methods = {
            "name": self._faker.name,
            "first_name": self._faker.first_name,
            "last_name": self._faker.last_name,
            "email": self._faker.email,
            "phone": self._faker.phone_number,
            "phone_number": self._faker.phone_number,
            "address": self._faker.address,
            "street_address": self._faker.street_address,
            "city": self._faker.city,
            "state": self._faker.state,
            "country": self._faker.country,
            "postcode": self._faker.postcode,
            "zipcode": self._faker.postcode,
            "company": self._faker.company,
            "job": self._faker.job,
            "text": self._faker.text,
            "sentence": self._faker.sentence,
            "paragraph": self._faker.paragraph,
            "word": self._faker.word,
            "url": self._faker.url,
            "uuid": self._faker.uuid4,
            "date": lambda: self._faker.date(),
            "datetime": lambda: self._faker.date_time().isoformat(),
            "user_name": self._faker.user_name,
            "password": self._faker.password,
        }

        if faker_type in faker_methods:
            return faker_methods[faker_type]()

        # Try to call the method directly on Faker
        if hasattr(self._faker, faker_type):
            method = getattr(self._faker, faker_type)
            if callable(method):
                return method()

        raise ExpressionError(f"faker:{faker_type}", f"Unknown faker type: {faker_type}")

    def _resolve_steps_reference(self, step_name: str, field_path: str) -> Any:
        """Resolve a reference to another step's data."""
        steps_data = self.context.get("__steps__", {})
        if step_name not in steps_data:
            raise ExpressionError(
                f"steps.{step_name}.{field_path}",
                f"Step '{step_name}' not found or not yet executed",
            )

        step_data = steps_data[step_name]
        return self._resolve_dotted_path(field_path, step_data)

    def _resolve_response_reference(self, field_path: str) -> Any:
        """Resolve a reference to the current response."""
        response_data = self.context.get("__response__", {})
        if not response_data:
            raise ExpressionError(f"response.{field_path}", "No response data available")

        return self._resolve_dotted_path(field_path, response_data)

    def _resolve_config_reference(self, config_path: str) -> Any:
        """Resolve a reference to configuration."""
        config_data = self.context.get("__config__", {})
        if not config_data:
            raise ExpressionError(f"config:{config_path}", "No configuration data available")

        return self._resolve_dotted_path(config_path, config_data)

    def _resolve_dotted_path(self, path: str, data: Any) -> Any:
        """Resolve a dotted path in a data structure."""
        parts = path.split(".")
        current = data

        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    raise ExpressionError(path, f"Key '{part}' not found")
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index]
                except (ValueError, IndexError):
                    raise ExpressionError(path, f"Invalid array index: {part}")
            else:
                raise ExpressionError(path, f"Cannot access '{part}' on {type(current).__name__}")

        return current

    def set_context(self, context: dict[str, Any]) -> None:
        """Set the variable context."""
        self.context = context

    def update_context(self, updates: dict[str, Any]) -> None:
        """Update the variable context with new values."""
        self.context.update(updates)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a single variable in the context."""
        self.context[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable from the context."""
        return self.context.get(name, default)

    def set_step_data(self, step_name: str, data: dict[str, Any]) -> None:
        """Store data from a completed step."""
        if "__steps__" not in self.context:
            self.context["__steps__"] = {}
        self.context["__steps__"][step_name] = data

    def set_response_data(self, data: dict[str, Any]) -> None:
        """Set the current response data."""
        self.context["__response__"] = data

    def clear_response_data(self) -> None:
        """Clear the current response data."""
        self.context.pop("__response__", None)


def extract_jsonpath(data: Any, path: str) -> Any:
    """Extract data using JSONPath expression.

    Args:
        data: The data to extract from.
        path: JSONPath expression (e.g., "$.field.nested", "$.items[0].id").

    Returns:
        Extracted value(s).
    """
    try:
        from jsonpath_ng import parse

        jsonpath_expr = parse(path)
        matches = jsonpath_expr.find(data)

        if not matches:
            return None
        elif len(matches) == 1:
            return matches[0].value
        else:
            return [m.value for m in matches]
    except ImportError:
        # Fallback to simple path resolution
        return _simple_path_extract(data, path)
    except Exception as e:
        raise ExpressionError(path, f"JSONPath extraction failed: {e}")


def _simple_path_extract(data: Any, path: str) -> Any:
    """Simple path extraction without jsonpath-ng."""
    # Remove leading $. if present
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]

    if not path:
        return data

    current = data
    # Split by . but handle array notation
    parts = re.split(r"\.(?![^\[]*\])", path)

    for part in parts:
        if not part:
            continue

        # Handle array notation like "items[0]" or "items[*]"
        array_match = re.match(r"(\w+)\[(\d+|\*)\]", part)
        if array_match:
            key = array_match.group(1)
            index = array_match.group(2)

            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

            if isinstance(current, list):
                if index == "*":
                    # Return all items
                    return current
                else:
                    idx = int(index)
                    if 0 <= idx < len(current):
                        current = current[idx]
                    else:
                        return None
            else:
                return None
        elif isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None

    return current

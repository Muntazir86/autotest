"""Response validator for workflow expectations.

Validates HTTP responses against workflow step expectations.
"""

from __future__ import annotations

import re
from typing import Any

from autotest.workflows.errors import ExpectationError
from autotest.workflows.expressions import extract_jsonpath


class ResponseValidator:
    """Validates responses against workflow expectations."""

    def __init__(self, workflow_name: str | None = None, step_name: str | None = None) -> None:
        """Initialize the validator.

        Args:
            workflow_name: Workflow name for error reporting.
            step_name: Step name for error reporting.
        """
        self.workflow_name = workflow_name
        self.step_name = step_name
        self.errors: list[ExpectationError] = []

    def validate(
        self,
        response_status: int,
        response_headers: dict[str, str],
        response_body: Any,
        response_time_ms: float,
        expect: dict[str, Any],
    ) -> list[ExpectationError]:
        """Validate a response against expectations.

        Args:
            response_status: HTTP status code.
            response_headers: Response headers.
            response_body: Response body (parsed JSON or raw).
            response_time_ms: Response time in milliseconds.
            expect: Expectation configuration.

        Returns:
            List of expectation errors.
        """
        self.errors = []

        # Validate status code
        expected_status = expect.get("status", [200])
        if isinstance(expected_status, int):
            expected_status = [expected_status]
        if response_status not in expected_status:
            self.errors.append(
                ExpectationError(
                    "status",
                    response_status,
                    expected_status,
                    self.workflow_name,
                    self.step_name,
                )
            )

        # Validate headers
        expected_headers = expect.get("headers", {})
        for header_name, expected_value in expected_headers.items():
            actual_value = response_headers.get(header_name) or response_headers.get(header_name.lower())
            if not self._validate_value(actual_value, expected_value):
                self.errors.append(
                    ExpectationError(
                        f"header '{header_name}'",
                        actual_value,
                        expected_value,
                        self.workflow_name,
                        self.step_name,
                    )
                )

        # Validate body
        expected_body = expect.get("body", {})
        if expected_body:
            self._validate_body(response_body, expected_body, "body")

        # Validate response time
        expected_time = expect.get("response_time_ms")
        if expected_time is not None:
            if isinstance(expected_time, dict):
                # Handle comparison operators
                self._validate_value_with_operators(response_time_ms, expected_time, "response_time_ms")
            elif response_time_ms > expected_time:
                self.errors.append(
                    ExpectationError(
                        "response_time_ms",
                        response_time_ms,
                        f"<= {expected_time}",
                        self.workflow_name,
                        self.step_name,
                    )
                )

        # Validate custom expressions
        custom_checks = expect.get("custom", [])
        for check_expr in custom_checks:
            if not self._evaluate_custom_check(check_expr, response_status, response_headers, response_body):
                self.errors.append(
                    ExpectationError(
                        f"custom check: {check_expr}",
                        "false",
                        "true",
                        self.workflow_name,
                        self.step_name,
                    )
                )

        return self.errors

    def _validate_body(self, actual: Any, expected: dict[str, Any], path: str) -> None:
        """Recursively validate body against expectations."""
        if isinstance(expected, dict):
            for key, expected_value in expected.items():
                # Handle special keys
                if key == "${length}":
                    if isinstance(actual, (list, str)):
                        self._validate_value_with_operators(len(actual), expected_value, f"{path}.length")
                    continue

                if key == "${each}":
                    if isinstance(actual, list):
                        for i, item in enumerate(actual):
                            self._validate_body(item, expected_value, f"{path}[{i}]")
                    continue

                # Regular key validation
                if isinstance(actual, dict):
                    actual_value = actual.get(key)
                else:
                    actual_value = None

                if isinstance(expected_value, dict) and not self._is_special_value(expected_value):
                    self._validate_body(actual_value, expected_value, f"{path}.{key}")
                elif not self._validate_value(actual_value, expected_value):
                    self.errors.append(
                        ExpectationError(
                            f"{path}.{key}",
                            actual_value,
                            expected_value,
                            self.workflow_name,
                            self.step_name,
                        )
                    )
        elif not self._validate_value(actual, expected):
            self.errors.append(
                ExpectationError(
                    path,
                    actual,
                    expected,
                    self.workflow_name,
                    self.step_name,
                )
            )

    def _validate_value(self, actual: Any, expected: Any) -> bool:
        """Validate a single value against an expectation."""
        if expected is None:
            return actual is None

        # Handle string expectations with special syntax
        if isinstance(expected, str):
            return self._validate_string_expectation(actual, expected)

        # Handle dict expectations (could be nested or special)
        if isinstance(expected, dict):
            if self._is_special_value(expected):
                return self._validate_special_value(actual, expected)
            # Regular dict comparison
            if not isinstance(actual, dict):
                return False
            for key, exp_val in expected.items():
                if key not in actual or not self._validate_value(actual[key], exp_val):
                    return False
            return True

        # Handle list expectations
        if isinstance(expected, list):
            if not isinstance(actual, list):
                return False
            if len(actual) != len(expected):
                return False
            return all(self._validate_value(a, e) for a, e in zip(actual, expected))

        # Direct comparison
        return actual == expected

    def _validate_string_expectation(self, actual: Any, expected: str) -> bool:
        """Validate against a string expectation with special syntax."""
        # Type check: ${type:string}
        type_match = re.match(r"^\$\{type:(\w+)\}$", expected)
        if type_match:
            expected_type = type_match.group(1)
            return self._check_type(actual, expected_type)

        # Regex: ${regex:pattern}
        regex_match = re.match(r"^\$\{regex:(.+)\}$", expected)
        if regex_match:
            pattern = regex_match.group(1)
            if actual is None:
                return False
            try:
                return bool(re.match(pattern, str(actual)))
            except re.error:
                return False

        # Greater than or equal: ${gte:value}
        gte_match = re.match(r"^\$\{gte:(.+)\}$", expected)
        if gte_match:
            try:
                threshold = float(gte_match.group(1))
                return actual is not None and float(actual) >= threshold
            except (ValueError, TypeError):
                return False

        # Less than or equal: ${lte:value}
        lte_match = re.match(r"^\$\{lte:(.+)\}$", expected)
        if lte_match:
            try:
                threshold = float(lte_match.group(1))
                return actual is not None and float(actual) <= threshold
            except (ValueError, TypeError):
                return False

        # Greater than: ${gt:value}
        gt_match = re.match(r"^\$\{gt:(.+)\}$", expected)
        if gt_match:
            try:
                threshold = float(gt_match.group(1))
                return actual is not None and float(actual) > threshold
            except (ValueError, TypeError):
                return False

        # Less than: ${lt:value}
        lt_match = re.match(r"^\$\{lt:(.+)\}$", expected)
        if lt_match:
            try:
                threshold = float(lt_match.group(1))
                return actual is not None and float(actual) < threshold
            except (ValueError, TypeError):
                return False

        # Between: ${between:min,max}
        between_match = re.match(r"^\$\{between:(.+),(.+)\}$", expected)
        if between_match:
            try:
                min_val = float(between_match.group(1))
                max_val = float(between_match.group(2))
                return actual is not None and min_val <= float(actual) <= max_val
            except (ValueError, TypeError):
                return False

        # Contains: ${contains:value}
        contains_match = re.match(r"^\$\{contains:(.+)\}$", expected)
        if contains_match:
            search_value = contains_match.group(1)
            if isinstance(actual, str):
                return search_value in actual
            elif isinstance(actual, list):
                return search_value in actual or any(search_value in str(item) for item in actual)
            return False

        # Extract marker: ${extract:name} - always passes (extraction happens elsewhere)
        extract_match = re.match(r"^\$\{extract:(\w+)\}$", expected)
        if extract_match:
            return True

        # Variable reference - compare as string
        if expected.startswith("${") and expected.endswith("}"):
            # This should have been resolved already, compare as-is
            return str(actual) == expected

        # Direct string comparison
        return actual == expected

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches an expected type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "float": float,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type is None:
            return False

        return isinstance(value, expected_python_type)

    def _is_special_value(self, value: dict[str, Any]) -> bool:
        """Check if a dict value is a special expectation."""
        special_keys = {"__extract__", "$gte", "$lte", "$gt", "$lt", "$between", "$contains", "$type", "$regex"}
        return bool(set(value.keys()) & special_keys)

    def _validate_special_value(self, actual: Any, expected: dict[str, Any]) -> bool:
        """Validate against a special dict expectation."""
        if "__extract__" in expected:
            return True  # Extraction marker, always passes

        if "$gte" in expected:
            try:
                return actual is not None and float(actual) >= float(expected["$gte"])
            except (ValueError, TypeError):
                return False

        if "$lte" in expected:
            try:
                return actual is not None and float(actual) <= float(expected["$lte"])
            except (ValueError, TypeError):
                return False

        if "$gt" in expected:
            try:
                return actual is not None and float(actual) > float(expected["$gt"])
            except (ValueError, TypeError):
                return False

        if "$lt" in expected:
            try:
                return actual is not None and float(actual) < float(expected["$lt"])
            except (ValueError, TypeError):
                return False

        if "$between" in expected:
            try:
                min_val, max_val = expected["$between"]
                return actual is not None and float(min_val) <= float(actual) <= float(max_val)
            except (ValueError, TypeError):
                return False

        if "$contains" in expected:
            search = expected["$contains"]
            if isinstance(actual, str):
                return search in actual
            elif isinstance(actual, list):
                return search in actual
            return False

        if "$type" in expected:
            return self._check_type(actual, expected["$type"])

        if "$regex" in expected:
            if actual is None:
                return False
            try:
                return bool(re.match(expected["$regex"], str(actual)))
            except re.error:
                return False

        return False

    def _validate_value_with_operators(self, actual: Any, expected: dict[str, Any], path: str) -> None:
        """Validate a value using operator dict."""
        if not self._validate_special_value(actual, expected):
            self.errors.append(
                ExpectationError(
                    path,
                    actual,
                    expected,
                    self.workflow_name,
                    self.step_name,
                )
            )

    def _evaluate_custom_check(
        self,
        expression: str,
        status: int,
        headers: dict[str, str],
        body: Any,
    ) -> bool:
        """Evaluate a custom check expression."""
        # Build context for evaluation
        context = {
            "response": {
                "status": status,
                "headers": headers,
                "body": body,
            }
        }

        # Simple expression evaluation
        # Support patterns like:
        # - response.body.total > 0
        # - response.body.items.length == 3
        # - response.status == 200

        try:
            # Replace response.body.X with actual values
            expr = expression

            # Handle response.body.X.length
            length_pattern = r"response\.body\.(\w+(?:\.\w+)*)\.length"
            for match in re.finditer(length_pattern, expr):
                path = match.group(1)
                value = extract_jsonpath(body, f"$.{path}")
                if isinstance(value, (list, str)):
                    expr = expr.replace(match.group(0), str(len(value)))
                else:
                    expr = expr.replace(match.group(0), "0")

            # Handle response.body.X
            body_pattern = r"response\.body\.(\w+(?:\.\w+)*)"
            for match in re.finditer(body_pattern, expr):
                path = match.group(1)
                value = extract_jsonpath(body, f"$.{path}")
                if isinstance(value, str):
                    expr = expr.replace(match.group(0), f"'{value}'")
                elif value is None:
                    expr = expr.replace(match.group(0), "None")
                else:
                    expr = expr.replace(match.group(0), str(value))

            # Handle response.status
            expr = expr.replace("response.status", str(status))

            # Evaluate the expression safely
            # Only allow basic comparisons
            allowed_chars = set("0123456789.+-*/<>=!() 'None\"andor")
            if all(c in allowed_chars or c.isalnum() for c in expr):
                return bool(eval(expr, {"__builtins__": {}}, {}))

            return False
        except Exception:
            return False

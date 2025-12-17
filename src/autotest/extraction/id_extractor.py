"""ID Extractor for detecting and extracting IDs from API responses.

This module provides strategies for detecting ID-like fields in responses
and extracting them with appropriate context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from autotest.schemas import APIOperation


# Common ID field patterns
ID_FIELD_PATTERNS = [
    re.compile(r"^id$", re.IGNORECASE),
    re.compile(r"^.*_id$", re.IGNORECASE),
    re.compile(r"^.*Id$"),
    re.compile(r"^uuid$", re.IGNORECASE),
    re.compile(r"^.*_uuid$", re.IGNORECASE),
    re.compile(r"^.*Uuid$"),
    re.compile(r"^identifier$", re.IGNORECASE),
    re.compile(r"^key$", re.IGNORECASE),
    re.compile(r"^pk$", re.IGNORECASE),
    re.compile(r"^.*_pk$", re.IGNORECASE),
]

# Fields to ignore (not IDs)
IGNORE_FIELDS = {
    "created_at",
    "updated_at",
    "deleted_at",
    "timestamp",
    "version",
    "count",
    "total",
    "page",
    "limit",
    "offset",
    "size",
}


@dataclass
class ExtractedID:
    """Represents an extracted ID with context."""

    field_name: str
    value: Any
    value_type: str  # "integer", "string", "uuid"
    source_path: str  # JSONPath-like path to the field
    resource_type: str | None  # Inferred resource type
    endpoint: str  # Source endpoint (e.g., "POST /users")
    parameter_name: str | None  # Matching path parameter name if any

    def __post_init__(self) -> None:
        # Determine value type
        if isinstance(self.value, int):
            self.value_type = "integer"
        elif self._is_uuid(self.value):
            self.value_type = "uuid"
        else:
            self.value_type = "string"

    @staticmethod
    def _is_uuid(value: Any) -> bool:
        """Check if a value looks like a UUID."""
        if not isinstance(value, str):
            return False
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        return bool(uuid_pattern.match(value))


class IDExtractor:
    """Extracts IDs from API responses using multiple strategies."""

    def __init__(
        self,
        custom_patterns: list[str] | None = None,
        ignore_fields: set[str] | None = None,
        path_parameters: set[str] | None = None,
    ) -> None:
        """Initialize the ID extractor.

        Args:
            custom_patterns: Additional regex patterns for ID field names.
            ignore_fields: Additional fields to ignore.
            path_parameters: Known path parameter names from the API schema.
        """
        self._patterns = list(ID_FIELD_PATTERNS)
        if custom_patterns:
            for pattern in custom_patterns:
                self._patterns.append(re.compile(pattern, re.IGNORECASE))

        self._ignore_fields = IGNORE_FIELDS.copy()
        if ignore_fields:
            self._ignore_fields.update(ignore_fields)

        self._path_parameters = path_parameters or set()

    def extract_from_response(
        self,
        response_body: Any,
        endpoint: str,
        resource_type: str | None = None,
        response_headers: dict[str, Any] | None = None,
    ) -> list[ExtractedID]:
        """Extract IDs from a response body and headers.

        Args:
            response_body: The parsed response body (dict, list, or primitive).
            endpoint: The endpoint that produced this response (e.g., "POST /users").
            resource_type: Inferred resource type for context.
            response_headers: Response headers to check for IDs.

        Returns:
            List of extracted IDs with context.
        """
        extracted: list[ExtractedID] = []

        # Extract from body
        if response_body is not None:
            self._extract_from_value(
                response_body,
                path="$",
                endpoint=endpoint,
                resource_type=resource_type,
                extracted=extracted,
            )

        # Extract from headers
        if response_headers:
            self._extract_from_headers(
                response_headers,
                endpoint=endpoint,
                resource_type=resource_type,
                extracted=extracted,
            )

        return extracted

    def _extract_from_value(
        self,
        value: Any,
        path: str,
        endpoint: str,
        resource_type: str | None,
        extracted: list[ExtractedID],
    ) -> None:
        """Recursively extract IDs from a value."""
        if isinstance(value, dict):
            for key, val in value.items():
                new_path = f"{path}.{key}"
                if self._is_id_field(key) and self._is_valid_id_value(val):
                    param_name = self._match_path_parameter(key)
                    extracted.append(
                        ExtractedID(
                            field_name=key,
                            value=val,
                            value_type="",  # Will be set in __post_init__
                            source_path=new_path,
                            resource_type=resource_type,
                            endpoint=endpoint,
                            parameter_name=param_name,
                        )
                    )
                # Recurse into nested structures
                self._extract_from_value(val, new_path, endpoint, resource_type, extracted)

        elif isinstance(value, list):
            for i, item in enumerate(value):
                new_path = f"{path}[{i}]"
                self._extract_from_value(item, new_path, endpoint, resource_type, extracted)

    def _extract_from_headers(
        self,
        headers: dict[str, Any],
        endpoint: str,
        resource_type: str | None,
        extracted: list[ExtractedID],
    ) -> None:
        """Extract IDs from response headers."""
        # Check Location header
        location = headers.get("location") or headers.get("Location")
        if location:
            # Try to extract ID from Location URL
            # Pattern: /resource/123 or /resource/uuid
            match = re.search(r"/([^/]+)$", str(location))
            if match:
                id_value = match.group(1)
                # Try to convert to int if possible
                try:
                    id_value = int(id_value)
                except ValueError:
                    pass

                extracted.append(
                    ExtractedID(
                        field_name="location_id",
                        value=id_value,
                        value_type="",
                        source_path="$header.Location",
                        resource_type=resource_type,
                        endpoint=endpoint,
                        parameter_name=None,
                    )
                )

        # Check X-Resource-Id header
        resource_id = headers.get("x-resource-id") or headers.get("X-Resource-Id")
        if resource_id:
            try:
                resource_id = int(resource_id)
            except (ValueError, TypeError):
                pass

            extracted.append(
                ExtractedID(
                    field_name="x_resource_id",
                    value=resource_id,
                    value_type="",
                    source_path="$header.X-Resource-Id",
                    resource_type=resource_type,
                    endpoint=endpoint,
                    parameter_name=None,
                )
            )

    def _is_id_field(self, field_name: str) -> bool:
        """Check if a field name looks like an ID field."""
        if field_name.lower() in self._ignore_fields:
            return False

        for pattern in self._patterns:
            if pattern.match(field_name):
                return True

        # Also check if it matches a known path parameter
        if field_name in self._path_parameters:
            return True

        return False

    def _is_valid_id_value(self, value: Any) -> bool:
        """Check if a value is a valid ID value."""
        if value is None:
            return False
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return isinstance(value, int) or value.is_integer()
        if isinstance(value, str):
            return len(value) > 0 and len(value) < 256
        return False

    def _match_path_parameter(self, field_name: str) -> str | None:
        """Try to match a field name to a known path parameter."""
        # Direct match
        if field_name in self._path_parameters:
            return field_name

        # Try common variations
        variations = [
            field_name,
            field_name.lower(),
            field_name.replace("_", ""),
            re.sub(r"_id$", "Id", field_name),
            re.sub(r"Id$", "_id", field_name),
        ]

        for param in self._path_parameters:
            param_lower = param.lower()
            for var in variations:
                if var.lower() == param_lower:
                    return param

        return None

    def add_path_parameters(self, parameters: set[str]) -> None:
        """Add path parameters to the known set."""
        self._path_parameters.update(parameters)

    @classmethod
    def from_schema(cls, schema: Any) -> IDExtractor:
        """Create an IDExtractor configured from an API schema.

        Args:
            schema: The API schema to extract path parameters from.

        Returns:
            Configured IDExtractor instance.
        """
        path_parameters: set[str] = set()

        # Try to extract path parameters from OpenAPI schema
        try:
            for operation in schema.get_all_operations():
                for param in getattr(operation, "path_parameters", {}).keys():
                    path_parameters.add(param)
        except Exception:
            pass

        return cls(path_parameters=path_parameters)

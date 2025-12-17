"""Resource type inference from API endpoints.

This module provides logic to infer resource types from API paths,
handling pluralization and nested resources.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# Common irregular plurals
IRREGULAR_PLURALS = {
    "people": "Person",
    "children": "Child",
    "men": "Man",
    "women": "Woman",
    "mice": "Mouse",
    "geese": "Goose",
    "teeth": "Tooth",
    "feet": "Foot",
    "data": "Data",
    "media": "Media",
    "criteria": "Criterion",
    "analyses": "Analysis",
    "statuses": "Status",
    "indices": "Index",
    "vertices": "Vertex",
    "matrices": "Matrix",
}


@dataclass
class InferredResource:
    """Information about an inferred resource."""

    resource_type: str
    parent_type: str | None
    parent_param: str | None
    path_segment: str

    def __str__(self) -> str:
        if self.parent_type:
            return f"{self.resource_type} (child of {self.parent_type})"
        return self.resource_type


class ResourceInferrer:
    """Infers resource types from API endpoint paths."""

    def __init__(self, custom_mappings: dict[str, str] | None = None) -> None:
        """Initialize the resource inferrer.

        Args:
            custom_mappings: Custom path segment to resource type mappings.
        """
        self._custom_mappings = custom_mappings or {}
        self._cache: dict[str, InferredResource] = {}

    def infer_from_path(self, path: str, method: str = "GET") -> InferredResource:
        """Infer resource type from an API path.

        Args:
            path: The API path (e.g., "/users/{userId}/orders").
            method: The HTTP method.

        Returns:
            InferredResource with type information.
        """
        cache_key = f"{method}:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = self._infer(path, method)
        self._cache[cache_key] = result
        return result

    def _infer(self, path: str, method: str) -> InferredResource:
        """Internal inference logic."""
        # Remove leading/trailing slashes and split
        path = path.strip("/")
        segments = path.split("/")

        # Filter out empty segments and version prefixes
        segments = [s for s in segments if s and not self._is_version_prefix(s)]

        if not segments:
            return InferredResource(
                resource_type="Unknown",
                parent_type=None,
                parent_param=None,
                path_segment="",
            )

        # Find resource segments (non-parameter segments)
        resource_segments: list[tuple[str, str | None]] = []  # (segment, following_param)

        i = 0
        while i < len(segments):
            segment = segments[i]
            if not self._is_path_parameter(segment):
                # Check if next segment is a parameter
                next_param = None
                if i + 1 < len(segments) and self._is_path_parameter(segments[i + 1]):
                    next_param = self._extract_param_name(segments[i + 1])
                resource_segments.append((segment, next_param))
            i += 1

        if not resource_segments:
            return InferredResource(
                resource_type="Unknown",
                parent_type=None,
                parent_param=None,
                path_segment="",
            )

        # The last resource segment is the main resource
        main_segment, main_param = resource_segments[-1]
        main_type = self._singularize(main_segment)

        # Check for parent resource
        parent_type = None
        parent_param = None
        if len(resource_segments) > 1:
            parent_segment, parent_param = resource_segments[-2]
            parent_type = self._singularize(parent_segment)

        return InferredResource(
            resource_type=main_type,
            parent_type=parent_type,
            parent_param=parent_param,
            path_segment=main_segment,
        )

    def infer_from_endpoint(self, method: str, path: str) -> str:
        """Get just the resource type string from an endpoint.

        Args:
            method: HTTP method.
            path: API path.

        Returns:
            Resource type string.
        """
        return self.infer_from_path(path, method).resource_type

    def get_path_parameters(self, path: str) -> list[str]:
        """Extract all path parameter names from a path.

        Args:
            path: The API path.

        Returns:
            List of parameter names.
        """
        params = []
        for segment in path.split("/"):
            if self._is_path_parameter(segment):
                params.append(self._extract_param_name(segment))
        return params

    def map_parameter_to_resource(self, param_name: str, path: str) -> str | None:
        """Try to map a path parameter to a resource type.

        Args:
            param_name: The parameter name (e.g., "userId").
            path: The API path for context.

        Returns:
            Resource type or None.
        """
        # Common patterns: userId -> User, order_id -> Order
        # Remove common suffixes
        base = param_name
        for suffix in ["_id", "Id", "_uuid", "Uuid", "_pk", "Pk"]:
            if param_name.endswith(suffix):
                base = param_name[: -len(suffix)]
                break

        # Capitalize first letter
        if base:
            return base[0].upper() + base[1:]

        return None

    def _is_path_parameter(self, segment: str) -> bool:
        """Check if a path segment is a parameter."""
        return segment.startswith("{") and segment.endswith("}")

    def _extract_param_name(self, segment: str) -> str:
        """Extract parameter name from a path parameter segment."""
        return segment.strip("{}")

    def _is_version_prefix(self, segment: str) -> bool:
        """Check if a segment is a version prefix like 'v1', 'api', etc."""
        return bool(re.match(r"^(v\d+|api|rest|graphql)$", segment, re.IGNORECASE))

    def _singularize(self, word: str) -> str:
        """Convert a plural word to singular and capitalize.

        Args:
            word: The word to singularize.

        Returns:
            Singularized and capitalized word.
        """
        # Check custom mappings first
        if word.lower() in self._custom_mappings:
            return self._custom_mappings[word.lower()]

        # Check irregular plurals
        if word.lower() in IRREGULAR_PLURALS:
            return IRREGULAR_PLURALS[word.lower()]

        # Apply common singularization rules
        singular = word

        # Remove hyphens and underscores, capitalize
        singular = singular.replace("-", "_")
        parts = singular.split("_")
        singular = parts[-1]  # Take the last part for compound paths

        # Common plural endings
        if singular.endswith("ies") and len(singular) > 3:
            singular = singular[:-3] + "y"
        elif singular.endswith("es") and len(singular) > 2:
            # Check for -ses, -xes, -zes, -ches, -shes
            if singular.endswith(("sses", "xes", "zes", "ches", "shes")):
                singular = singular[:-2]
            elif singular.endswith("oes"):
                singular = singular[:-2]
            else:
                singular = singular[:-1]  # Just remove 's' for other -es
        elif singular.endswith("s") and not singular.endswith("ss") and len(singular) > 1:
            singular = singular[:-1]

        # Capitalize first letter
        if singular:
            singular = singular[0].upper() + singular[1:]

        return singular

    def add_custom_mapping(self, path_segment: str, resource_type: str) -> None:
        """Add a custom path segment to resource type mapping.

        Args:
            path_segment: The path segment (e.g., "users").
            resource_type: The resource type (e.g., "User").
        """
        self._custom_mappings[path_segment.lower()] = resource_type
        self._cache.clear()

"""Thread-safe ID storage for extracted IDs.

This module provides a storage system for IDs extracted from API responses,
with support for lookup by resource type, parameter name, and endpoint.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterator

from autotest.extraction.id_extractor import ExtractedID


# Thread-local storage for the current ID store
_store_storage = threading.local()


def get_id_store() -> IDStore | None:
    """Get the current thread's ID store."""
    return getattr(_store_storage, "store", None)


def set_id_store(store: IDStore | None) -> None:
    """Set the current thread's ID store."""
    _store_storage.store = store


@dataclass
class StoredID:
    """An ID stored with metadata."""

    extracted_id: ExtractedID
    stored_at: float
    is_deleted: bool = False

    @property
    def value(self) -> Any:
        return self.extracted_id.value

    @property
    def field_name(self) -> str:
        return self.extracted_id.field_name

    @property
    def resource_type(self) -> str | None:
        return self.extracted_id.resource_type

    @property
    def parameter_name(self) -> str | None:
        return self.extracted_id.parameter_name

    @property
    def endpoint(self) -> str:
        return self.extracted_id.endpoint

    @property
    def value_type(self) -> str:
        return self.extracted_id.value_type


class IDStore:
    """Thread-safe storage for extracted IDs.

    Provides efficient lookup by:
    - Resource type (e.g., "User", "Order")
    - Path parameter name (e.g., "userId", "orderId")
    - Source endpoint (e.g., "POST /users")
    """

    def __init__(
        self,
        max_ids_per_type: int = 100,
        ttl_seconds: float | None = None,
    ) -> None:
        """Initialize the ID store.

        Args:
            max_ids_per_type: Maximum IDs to store per resource type (LRU eviction).
            ttl_seconds: Time-to-live for stored IDs (None = no expiry).
        """
        self._lock = threading.RLock()
        self._max_ids = max_ids_per_type
        self._ttl = ttl_seconds

        # Storage indexed by different keys
        self._by_resource_type: dict[str, list[StoredID]] = defaultdict(list)
        self._by_parameter: dict[str, list[StoredID]] = defaultdict(list)
        self._by_endpoint: dict[str, list[StoredID]] = defaultdict(list)
        self._by_field_name: dict[str, list[StoredID]] = defaultdict(list)

        # All stored IDs for iteration
        self._all_ids: list[StoredID] = []

        # Relationships between resources
        self._relationships: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))

    def store(self, extracted_id: ExtractedID) -> None:
        """Store an extracted ID.

        Args:
            extracted_id: The extracted ID to store.
        """
        with self._lock:
            stored = StoredID(
                extracted_id=extracted_id,
                stored_at=time.time(),
            )

            self._all_ids.append(stored)

            # Index by resource type
            if extracted_id.resource_type:
                self._by_resource_type[extracted_id.resource_type].append(stored)
                self._enforce_limit(self._by_resource_type[extracted_id.resource_type])

            # Index by parameter name
            if extracted_id.parameter_name:
                self._by_parameter[extracted_id.parameter_name].append(stored)
                self._enforce_limit(self._by_parameter[extracted_id.parameter_name])

            # Index by endpoint
            self._by_endpoint[extracted_id.endpoint].append(stored)
            self._enforce_limit(self._by_endpoint[extracted_id.endpoint])

            # Index by field name
            self._by_field_name[extracted_id.field_name].append(stored)
            self._enforce_limit(self._by_field_name[extracted_id.field_name])

    def store_all(self, extracted_ids: list[ExtractedID]) -> None:
        """Store multiple extracted IDs.

        Args:
            extracted_ids: List of extracted IDs to store.
        """
        for extracted_id in extracted_ids:
            self.store(extracted_id)

    def get_for_parameter(
        self,
        param_name: str,
        prefer: str = "latest",
        value_type: str | None = None,
    ) -> Any | None:
        """Get an ID value for a path parameter.

        Args:
            param_name: The parameter name to look up.
            prefer: Selection strategy ("latest", "random", "first").
            value_type: Preferred value type ("integer", "string", "uuid").

        Returns:
            An ID value or None if not found.
        """
        with self._lock:
            # Try direct parameter match
            ids = self._get_valid_ids(self._by_parameter.get(param_name, []))

            # Try field name match
            if not ids:
                ids = self._get_valid_ids(self._by_field_name.get(param_name, []))

            # Try variations
            if not ids:
                variations = self._get_parameter_variations(param_name)
                for var in variations:
                    ids = self._get_valid_ids(self._by_parameter.get(var, []))
                    if ids:
                        break
                    ids = self._get_valid_ids(self._by_field_name.get(var, []))
                    if ids:
                        break

            if not ids:
                return None

            # Filter by value type if specified
            if value_type:
                typed_ids = [i for i in ids if i.value_type == value_type]
                if typed_ids:
                    ids = typed_ids

            return self._select_id(ids, prefer)

    def get_for_resource(
        self,
        resource_type: str,
        prefer: str = "latest",
    ) -> Any | None:
        """Get an ID value for a resource type.

        Args:
            resource_type: The resource type to look up.
            prefer: Selection strategy ("latest", "random", "first").

        Returns:
            An ID value or None if not found.
        """
        with self._lock:
            ids = self._get_valid_ids(self._by_resource_type.get(resource_type, []))
            if not ids:
                return None
            return self._select_id(ids, prefer)

    def get_all_for_parameter(self, param_name: str) -> list[Any]:
        """Get all ID values for a parameter.

        Args:
            param_name: The parameter name to look up.

        Returns:
            List of all ID values for the parameter.
        """
        with self._lock:
            ids = self._get_valid_ids(self._by_parameter.get(param_name, []))
            return [i.value for i in ids]

    def get_all_for_resource(self, resource_type: str) -> list[Any]:
        """Get all ID values for a resource type.

        Args:
            resource_type: The resource type to look up.

        Returns:
            List of all ID values for the resource type.
        """
        with self._lock:
            ids = self._get_valid_ids(self._by_resource_type.get(resource_type, []))
            return [i.value for i in ids]

    def mark_deleted(self, value: Any, resource_type: str | None = None) -> None:
        """Mark an ID as deleted (e.g., after DELETE request).

        Args:
            value: The ID value to mark as deleted.
            resource_type: Optional resource type to narrow the search.
        """
        with self._lock:
            for stored in self._all_ids:
                if stored.value == value:
                    if resource_type is None or stored.resource_type == resource_type:
                        stored.is_deleted = True

    def add_relationship(
        self,
        parent_type: str,
        parent_id: Any,
        relation: str,
        child_id: Any,
    ) -> None:
        """Add a relationship between resources.

        Args:
            parent_type: The parent resource type.
            parent_id: The parent resource ID.
            relation: The relationship name.
            child_id: The child resource ID.
        """
        with self._lock:
            key = f"{parent_type}:{parent_id}"
            self._relationships[key][relation].append(child_id)

    def get_related(
        self,
        parent_type: str,
        parent_id: Any,
        relation: str,
    ) -> list[Any]:
        """Get related IDs for a parent resource.

        Args:
            parent_type: The parent resource type.
            parent_id: The parent resource ID.
            relation: The relationship name.

        Returns:
            List of related IDs.
        """
        with self._lock:
            key = f"{parent_type}:{parent_id}"
            return list(self._relationships.get(key, {}).get(relation, []))

    def clear(self, resource_type: str | None = None) -> None:
        """Clear stored IDs.

        Args:
            resource_type: If specified, only clear IDs for this resource type.
        """
        with self._lock:
            if resource_type is None:
                self._by_resource_type.clear()
                self._by_parameter.clear()
                self._by_endpoint.clear()
                self._by_field_name.clear()
                self._all_ids.clear()
                self._relationships.clear()
            else:
                # Remove IDs for specific resource type
                ids_to_remove = set(id(i) for i in self._by_resource_type.get(resource_type, []))
                self._by_resource_type.pop(resource_type, None)

                # Clean up other indexes
                for key in list(self._by_parameter.keys()):
                    self._by_parameter[key] = [
                        i for i in self._by_parameter[key] if id(i) not in ids_to_remove
                    ]
                for key in list(self._by_endpoint.keys()):
                    self._by_endpoint[key] = [
                        i for i in self._by_endpoint[key] if id(i) not in ids_to_remove
                    ]
                for key in list(self._by_field_name.keys()):
                    self._by_field_name[key] = [
                        i for i in self._by_field_name[key] if id(i) not in ids_to_remove
                    ]
                self._all_ids = [i for i in self._all_ids if id(i) not in ids_to_remove]

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of stored IDs."""
        with self._lock:
            return {
                "total_ids": len(self._all_ids),
                "by_resource_type": {k: len(v) for k, v in self._by_resource_type.items()},
                "by_parameter": {k: len(v) for k, v in self._by_parameter.items()},
                "active_ids": len([i for i in self._all_ids if not i.is_deleted]),
                "deleted_ids": len([i for i in self._all_ids if i.is_deleted]),
            }

    def _get_valid_ids(self, ids: list[StoredID]) -> list[StoredID]:
        """Filter out deleted and expired IDs."""
        now = time.time()
        valid = []
        for stored in ids:
            if stored.is_deleted:
                continue
            if self._ttl and (now - stored.stored_at) > self._ttl:
                continue
            valid.append(stored)
        return valid

    def _select_id(self, ids: list[StoredID], prefer: str) -> Any:
        """Select an ID based on preference strategy."""
        if not ids:
            return None

        if prefer == "latest":
            return max(ids, key=lambda i: i.stored_at).value
        elif prefer == "first":
            return min(ids, key=lambda i: i.stored_at).value
        elif prefer == "random":
            import random
            return random.choice(ids).value
        else:
            return ids[-1].value

    def _enforce_limit(self, ids: list[StoredID]) -> None:
        """Enforce the maximum IDs limit (LRU eviction)."""
        while len(ids) > self._max_ids:
            ids.pop(0)

    def _get_parameter_variations(self, param_name: str) -> list[str]:
        """Generate common variations of a parameter name."""
        import re

        variations = []

        # snake_case to camelCase
        if "_" in param_name:
            parts = param_name.split("_")
            camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
            variations.append(camel)

        # camelCase to snake_case
        snake = re.sub(r"([A-Z])", r"_\1", param_name).lower().lstrip("_")
        if snake != param_name:
            variations.append(snake)

        # Remove common suffixes/prefixes
        for suffix in ["_id", "Id", "_uuid", "Uuid"]:
            if param_name.endswith(suffix):
                base = param_name[: -len(suffix)]
                variations.append(base)
                variations.append(base + "_id")
                variations.append(base + "Id")

        # Add 'id' suffix if not present
        if not param_name.lower().endswith("id"):
            variations.append(param_name + "_id")
            variations.append(param_name + "Id")

        return variations

    def __iter__(self) -> Iterator[StoredID]:
        """Iterate over all stored IDs."""
        with self._lock:
            return iter(list(self._all_ids))

    def __len__(self) -> int:
        """Get the total number of stored IDs."""
        with self._lock:
            return len(self._all_ids)

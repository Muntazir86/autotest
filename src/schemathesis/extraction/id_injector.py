"""ID Injector for injecting stored IDs into test cases.

This module provides logic to inject stored IDs into path parameters,
query parameters, and request bodies.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from schemathesis.extraction.id_store import IDStore
    from schemathesis.extraction.resource_inferrer import ResourceInferrer
    from schemathesis.generation.case import Case


class IDInjector:
    """Injects stored IDs into test cases."""

    def __init__(
        self,
        id_store: IDStore,
        resource_inferrer: ResourceInferrer,
        prefer: str = "latest",
        fallback_to_generated: bool = True,
        inject_into_body: bool = True,
        inject_into_query: bool = True,
        verbose: bool = False,
    ) -> None:
        """Initialize the ID injector.

        Args:
            id_store: The ID store to get IDs from.
            resource_inferrer: Resource inferrer for type mapping.
            prefer: ID selection strategy ("latest", "random", "first").
            fallback_to_generated: If True, use generated values when no ID found.
            inject_into_body: Whether to inject IDs into request bodies.
            inject_into_query: Whether to inject IDs into query parameters.
            verbose: Whether to log injection decisions.
        """
        self._store = id_store
        self._inferrer = resource_inferrer
        self._prefer = prefer
        self._fallback = fallback_to_generated
        self._inject_body = inject_into_body
        self._inject_query = inject_into_query
        self._verbose = verbose
        self._injection_log: list[dict[str, Any]] = []

    def inject_into_case(self, case: Case) -> Case:
        """Inject stored IDs into a test case.

        Args:
            case: The test case to modify.

        Returns:
            The modified test case (same object, modified in place).
        """
        # Inject into path parameters
        self._inject_path_parameters(case)

        # Inject into query parameters
        if self._inject_query:
            self._inject_query_parameters(case)

        # Inject into body
        if self._inject_body:
            self._inject_body_parameters(case)

        return case

    def _inject_path_parameters(self, case: Case) -> None:
        """Inject IDs into path parameters."""
        if not case.path_parameters:
            return

        for param_name, current_value in list(case.path_parameters.items()):
            # Try to get a stored ID for this parameter
            stored_id = self._store.get_for_parameter(
                param_name,
                prefer=self._prefer,
            )

            if stored_id is not None:
                case.path_parameters[param_name] = stored_id
                self._log_injection(
                    location="path_parameter",
                    param_name=param_name,
                    old_value=current_value,
                    new_value=stored_id,
                )
            elif not self._fallback:
                # If no fallback, we might want to skip this case
                pass

    def _inject_query_parameters(self, case: Case) -> None:
        """Inject IDs into query parameters."""
        if not case.query:
            return

        for param_name, current_value in list(case.query.items()):
            # Check if this looks like an ID parameter
            if not self._is_id_like_parameter(param_name):
                continue

            # Try to get a stored ID
            stored_id = self._store.get_for_parameter(
                param_name,
                prefer=self._prefer,
            )

            if stored_id is not None:
                case.query[param_name] = stored_id
                self._log_injection(
                    location="query_parameter",
                    param_name=param_name,
                    old_value=current_value,
                    new_value=stored_id,
                )

    def _inject_body_parameters(self, case: Case) -> None:
        """Inject IDs into request body."""
        from schemathesis.core import NOT_SET

        if case.body is None or isinstance(case.body, type(NOT_SET)):
            return

        if isinstance(case.body, dict):
            self._inject_into_dict(case.body, "body")

    def _inject_into_dict(self, data: dict, path: str) -> None:
        """Recursively inject IDs into a dictionary."""
        for key, value in list(data.items()):
            current_path = f"{path}.{key}"

            if isinstance(value, dict):
                self._inject_into_dict(value, current_path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        self._inject_into_dict(item, f"{current_path}[{i}]")
            elif self._is_id_like_parameter(key):
                # Try to inject an ID
                stored_id = self._store.get_for_parameter(
                    key,
                    prefer=self._prefer,
                )

                if stored_id is not None:
                    # Type coercion if needed
                    if isinstance(value, int) and isinstance(stored_id, str):
                        try:
                            stored_id = int(stored_id)
                        except ValueError:
                            pass
                    elif isinstance(value, str) and isinstance(stored_id, int):
                        stored_id = str(stored_id)

                    data[key] = stored_id
                    self._log_injection(
                        location="body",
                        param_name=key,
                        old_value=value,
                        new_value=stored_id,
                        path=current_path,
                    )

    def _is_id_like_parameter(self, name: str) -> bool:
        """Check if a parameter name looks like an ID field."""
        patterns = [
            r"^id$",
            r".*_id$",
            r".*Id$",
            r"^uuid$",
            r".*_uuid$",
            r".*Uuid$",
            r".*_pk$",
            r".*Pk$",
        ]

        for pattern in patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return True

        return False

    def _log_injection(
        self,
        location: str,
        param_name: str,
        old_value: Any,
        new_value: Any,
        path: str | None = None,
    ) -> None:
        """Log an injection decision."""
        entry = {
            "location": location,
            "param_name": param_name,
            "old_value": old_value,
            "new_value": new_value,
            "path": path,
        }
        self._injection_log.append(entry)

        if self._verbose:
            print(f"[ID Injection] {location}: {param_name} = {new_value} (was: {old_value})")

    def get_injection_log(self) -> list[dict[str, Any]]:
        """Get the log of all injection decisions."""
        return list(self._injection_log)

    def clear_log(self) -> None:
        """Clear the injection log."""
        self._injection_log.clear()

    def get_injection_summary(self) -> dict[str, Any]:
        """Get a summary of injections performed."""
        by_location: dict[str, int] = {}
        for entry in self._injection_log:
            loc = entry["location"]
            by_location[loc] = by_location.get(loc, 0) + 1

        return {
            "total_injections": len(self._injection_log),
            "by_location": by_location,
        }


def create_injector_from_store(
    id_store: IDStore,
    prefer: str = "latest",
    verbose: bool = False,
) -> IDInjector:
    """Create an ID injector with default settings.

    Args:
        id_store: The ID store to use.
        prefer: ID selection strategy.
        verbose: Whether to log injection decisions.

    Returns:
        Configured IDInjector instance.
    """
    from schemathesis.extraction.resource_inferrer import ResourceInferrer

    return IDInjector(
        id_store=id_store,
        resource_inferrer=ResourceInferrer(),
        prefer=prefer,
        verbose=verbose,
    )

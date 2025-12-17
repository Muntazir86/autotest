"""Configuration for ID extraction feature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from autotest.config._diff_base import DiffBase


@dataclass(repr=False)
class IDExtractionConfig(DiffBase):
    """Configuration for automatic ID extraction and injection."""

    enabled: bool
    prefer: str  # "latest", "random", "first"
    fallback_to_generated: bool
    inject_into_body: bool
    inject_into_query: bool
    custom_patterns: list[str]
    ignore_fields: list[str]
    verbose: bool

    __slots__ = (
        "enabled",
        "prefer",
        "fallback_to_generated",
        "inject_into_body",
        "inject_into_query",
        "custom_patterns",
        "ignore_fields",
        "verbose",
    )

    def __init__(
        self,
        *,
        enabled: bool = False,
        prefer: str = "latest",
        fallback_to_generated: bool = True,
        inject_into_body: bool = True,
        inject_into_query: bool = True,
        custom_patterns: list[str] | None = None,
        ignore_fields: list[str] | None = None,
        verbose: bool = False,
    ) -> None:
        self.enabled = enabled
        self.prefer = prefer
        self.fallback_to_generated = fallback_to_generated
        self.inject_into_body = inject_into_body
        self.inject_into_query = inject_into_query
        self.custom_patterns = custom_patterns or []
        self.ignore_fields = ignore_fields or []
        self.verbose = verbose

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IDExtractionConfig:
        return cls(
            enabled=data.get("enabled", False),
            prefer=data.get("prefer", "latest"),
            fallback_to_generated=data.get("fallback-to-generated", True),
            inject_into_body=data.get("inject-into-body", True),
            inject_into_query=data.get("inject-into-query", True),
            custom_patterns=data.get("custom-patterns", []),
            ignore_fields=data.get("ignore-fields", []),
            verbose=data.get("verbose", False),
        )

    def update(
        self,
        *,
        enabled: bool | None = None,
        prefer: str | None = None,
        fallback_to_generated: bool | None = None,
        inject_into_body: bool | None = None,
        inject_into_query: bool | None = None,
        custom_patterns: list[str] | None = None,
        ignore_fields: list[str] | None = None,
        verbose: bool | None = None,
    ) -> None:
        if enabled is not None:
            self.enabled = enabled
        if prefer is not None:
            self.prefer = prefer
        if fallback_to_generated is not None:
            self.fallback_to_generated = fallback_to_generated
        if inject_into_body is not None:
            self.inject_into_body = inject_into_body
        if inject_into_query is not None:
            self.inject_into_query = inject_into_query
        if custom_patterns is not None:
            self.custom_patterns = custom_patterns
        if ignore_fields is not None:
            self.ignore_fields = ignore_fields
        if verbose is not None:
            self.verbose = verbose

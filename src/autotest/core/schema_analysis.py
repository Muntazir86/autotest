from __future__ import annotations

from typing import Protocol

from autotest.config import AutotestWarning


class SchemaWarning(Protocol):
    """Shared interface for static schema analysis warnings."""

    operation_label: str | None

    @property
    def kind(self) -> AutotestWarning: ...

    @property
    def message(self) -> str: ...

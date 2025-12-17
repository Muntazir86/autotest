from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autotest.pytest.lazy import LazySchema


def from_fixture(name: str) -> LazySchema:
    """Create a lazy schema loader that resolves a pytest fixture at test runtime.

    Args:
        name: Name of the pytest fixture that returns a schema object

    Example:
        ```python
        import pytest
        import autotest

        @pytest.fixture
        def api_schema():
            return autotest.openapi.from_url("https://api.example.com/openapi.json")

        # Create lazy schema from fixture
        schema = Autotest.pytest.from_fixture("api_schema")

        # Use with parametrize to generate tests
        @schema.parametrize()
        def test_api(case):
            case.call_and_validate()
        ```

    """
    from autotest.pytest.lazy import LazySchema

    return LazySchema(name)

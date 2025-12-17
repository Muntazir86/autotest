"""Hook integration for HTML report generation.

This module provides hooks that integrate the reporting system
with Schemathesis test execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from schemathesis.reporting.collector import DataCollector, get_collector, set_collector
from schemathesis.reporting.html_generator import HTMLReportGenerator

if TYPE_CHECKING:
    from schemathesis.core.transport import Response
    from schemathesis.generation.case import Case
    from schemathesis.hooks import HookContext


# Global state
_enabled: bool = False
_output_path: Path | None = None
_title: str = "API Test Report"
_include_passed_details: bool = False
_max_body_size: int = 10240
_sanitize_headers: list[str] | None = None


def enable_html_report(
    output_path: str | Path,
    title: str = "API Test Report",
    include_passed_details: bool = False,
    max_body_size: int = 10240,
    sanitize_headers: list[str] | None = None,
    api_name: str = "",
    api_version: str = "",
    base_url: str = "",
) -> None:
    """Enable HTML report generation.

    Args:
        output_path: Path where the HTML report will be written.
        title: Title for the report.
        include_passed_details: Include full details for passed tests.
        max_body_size: Maximum body size to capture (bytes).
        sanitize_headers: Additional headers to sanitize.
        api_name: Name of the API being tested.
        api_version: Version of the API.
        base_url: Base URL of the API.
    """
    global _enabled, _output_path, _title, _include_passed_details
    global _max_body_size, _sanitize_headers

    _enabled = True
    _output_path = Path(output_path)
    _title = title
    _include_passed_details = include_passed_details
    _max_body_size = max_body_size
    _sanitize_headers = sanitize_headers

    # Create and set the collector
    collector = DataCollector(
        api_name=api_name,
        api_version=api_version,
        base_url=base_url,
        max_body_size=max_body_size,
        sanitize_headers=sanitize_headers,
        include_passed_details=include_passed_details,
    )
    set_collector(collector)

    # Register hooks
    _register_hooks()


def disable_html_report() -> None:
    """Disable HTML report generation."""
    global _enabled

    _enabled = False
    set_collector(None)

    # Unregister hooks
    _unregister_hooks()


def is_enabled() -> bool:
    """Check if HTML report generation is enabled."""
    return _enabled


def generate_report() -> Path | None:
    """Generate the HTML report from collected data.

    Returns:
        Path to the generated report, or None if not enabled.
    """
    if not _enabled or _output_path is None:
        return None

    collector = get_collector()
    if collector is None:
        return None

    # Finish the run
    run_info = collector.finish()

    # Generate the report
    generator = HTMLReportGenerator(
        title=_title,
        include_passed_details=_include_passed_details,
    )

    return generator.generate(run_info, _output_path)


def _register_hooks() -> None:
    """Register the reporting hooks with Schemathesis."""
    from schemathesis.hooks import GLOBAL_HOOK_DISPATCHER

    # Register after_call hook for data collection
    GLOBAL_HOOK_DISPATCHER.register_hook_with_name(_after_call_hook, "after_call")


def _unregister_hooks() -> None:
    """Unregister the reporting hooks."""
    from schemathesis.hooks import GLOBAL_HOOK_DISPATCHER

    GLOBAL_HOOK_DISPATCHER.unregister(_after_call_hook)


def _after_call_hook(context: HookContext, case: Case, response: Response) -> None:
    """Hook called after each API call to collect data."""
    if not _enabled:
        return

    collector = get_collector()
    if collector is None:
        return

    try:
        # Determine check results - we'll get these from the check execution
        # For now, we record basic pass/fail based on status code
        check_results: list[tuple[str, bool, str | None]] = []

        # Basic status code check
        is_server_error = response.status_code >= 500
        check_results.append((
            "not_a_server_error",
            not is_server_error,
            f"Server returned {response.status_code}" if is_server_error else None,
        ))

        # Record the test
        collector.record_test(
            case=case,
            response=response,
            check_results=check_results,
            failure_reason=f"Server error: {response.status_code}" if is_server_error else None,
        )

    except Exception:
        # Don't let reporting errors break tests
        pass


def set_phase(phase: str) -> None:
    """Set the current test phase for the collector."""
    collector = get_collector()
    if collector:
        collector.set_phase(phase)


def get_collection_summary() -> dict[str, Any] | None:
    """Get a summary of collected data."""
    collector = get_collector()
    if collector:
        return collector.get_summary()
    return None

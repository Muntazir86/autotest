"""Data collector for capturing test execution data.

This module provides a thread-safe collector that hooks into Autotest
execution to capture request/response data for report generation.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Generator

from autotest.reporting.models import (
    CheckResult,
    TestCaseResult,
    TestRunInfo,
    TestStatus,
)

if TYPE_CHECKING:
    from autotest.core.transport import Response
    from autotest.generation.case import Case

# Thread-local storage for the current collector
_collector_storage = threading.local()


def get_collector() -> DataCollector | None:
    """Get the current thread's data collector."""
    return getattr(_collector_storage, "collector", None)


def set_collector(collector: DataCollector | None) -> None:
    """Set the current thread's data collector."""
    _collector_storage.collector = collector


@contextmanager
def collector_context(collector: DataCollector) -> Generator[DataCollector, None, None]:
    """Context manager for setting up a collector for the current thread."""
    previous = get_collector()
    set_collector(collector)
    try:
        yield collector
    finally:
        set_collector(previous)


class DataCollector:
    """Collects test execution data for report generation.

    Thread-safe collector that captures request/response data during test runs.
    """

    def __init__(
        self,
        api_name: str = "",
        api_version: str = "",
        base_url: str = "",
        max_body_size: int = 10240,
        sanitize_headers: list[str] | None = None,
        include_passed_details: bool = False,
    ) -> None:
        """Initialize the data collector.

        Args:
            api_name: Name of the API being tested.
            api_version: Version of the API.
            base_url: Base URL of the API.
            max_body_size: Maximum body size to capture (bytes).
            sanitize_headers: Additional headers to sanitize.
            include_passed_details: Whether to include full details for passed tests.
        """
        self._lock = threading.Lock()
        self._run_info = TestRunInfo.create(
            api_name=api_name,
            api_version=api_version,
            base_url=base_url,
        )
        self._max_body_size = max_body_size
        self._sanitize_headers = set(sanitize_headers or [])
        self._include_passed_details = include_passed_details
        self._current_phase: str = "unknown"

    @property
    def run_info(self) -> TestRunInfo:
        """Get the current test run info."""
        return self._run_info

    def set_phase(self, phase: str) -> None:
        """Set the current test phase."""
        with self._lock:
            self._current_phase = phase

    def record_test(
        self,
        case: Case,
        response: Response,
        check_results: list[tuple[str, bool, str | None]],
        failure_reason: str | None = None,
    ) -> None:
        """Record a test case execution.

        Args:
            case: The test case that was executed.
            response: The response received.
            check_results: List of (check_name, passed, message) tuples.
            failure_reason: Overall failure reason if the test failed.
        """
        # Convert check results to CheckResult objects
        checks = [
            CheckResult(
                name=name,
                status=TestStatus.PASSED if passed else TestStatus.FAILED,
                message=message,
            )
            for name, passed, message in check_results
        ]

        # Create the test case result
        result = TestCaseResult.create(
            case=case,
            response=response,
            phase=self._current_phase,
            check_results=checks,
            failure_reason=failure_reason,
        )

        # Truncate body if needed
        self._truncate_body(result)

        # Add to run info (thread-safe)
        with self._lock:
            self._run_info.add_result(result)

    def record_from_recorder(
        self,
        recorder: Any,
        phase: str,
    ) -> None:
        """Record test results from a ScenarioRecorder.

        Args:
            recorder: The ScenarioRecorder containing test data.
            phase: The test phase name.
        """
        self._current_phase = phase

        for case_id, case_node in recorder.cases.items():
            case = case_node.value
            interaction = recorder.interactions.get(case_id)

            if interaction is None or interaction.response is None:
                continue

            response = interaction.response

            # Get check results for this case
            check_nodes = recorder.checks.get(case_id, [])
            check_results: list[tuple[str, bool, str | None]] = []
            failure_reason = None

            for check_node in check_nodes:
                from autotest.engine import Status

                passed = check_node.status == Status.SUCCESS
                message = None
                if check_node.failure_info:
                    message = str(check_node.failure_info.failure)
                    if not failure_reason:
                        failure_reason = message
                check_results.append((check_node.name, passed, message))

            self.record_test(case, response, check_results, failure_reason)

    def _truncate_body(self, result: TestCaseResult) -> None:
        """Truncate large bodies in the result."""
        # Truncate request body
        if result.request.body_size and result.request.body_size > self._max_body_size:
            if isinstance(result.request.body, str):
                result.request.body = (
                    result.request.body[: self._max_body_size]
                    + f"... [truncated, total {result.request.body_size} bytes]"
                )

        # Truncate response body
        if result.response.body_size and result.response.body_size > self._max_body_size:
            if isinstance(result.response.body, str):
                result.response.body = (
                    result.response.body[: self._max_body_size]
                    + f"... [truncated, total {result.response.body_size} bytes]"
                )

    def finish(self) -> TestRunInfo:
        """Finish the test run and return the final run info."""
        with self._lock:
            self._run_info.finish()
            return self._run_info

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the current test run."""
        with self._lock:
            return {
                "total": self._run_info.total_tests,
                "passed": self._run_info.passed,
                "failed": self._run_info.failed,
                "errored": self._run_info.errored,
                "skipped": self._run_info.skipped,
                "endpoints_tested": len(self._run_info.endpoints),
            }

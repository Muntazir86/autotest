"""Data models for HTML report generation.

These models capture all request/response data during test execution
and provide structured data for report generation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    """Status of a test case execution."""

    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"
    SKIPPED = "skipped"


@dataclass
class RequestData:
    """Captured HTTP request data."""

    timestamp: str
    method: str
    url: str
    path: str
    path_parameters: dict[str, Any]
    query_parameters: dict[str, Any]
    headers: dict[str, str]
    body: Any
    body_size: int | None

    @classmethod
    def from_case_and_response(
        cls,
        case: Any,
        response: Any,
        timestamp: datetime | None = None,
    ) -> RequestData:
        """Create RequestData from a Case and Response object."""
        from schemathesis.core import NOT_SET

        if timestamp is None:
            timestamp = datetime.utcnow()

        # Extract request info from the response's prepared request
        request = response.request
        url = str(request.url) if request.url else ""

        # Get body from case
        body = case.body if not isinstance(case.body, type(NOT_SET)) else None
        body_size = None
        if body is not None:
            if isinstance(body, (str, bytes)):
                body_size = len(body)
            else:
                try:
                    import json
                    body_size = len(json.dumps(body))
                except (TypeError, ValueError):
                    pass

        # Sanitize headers (remove sensitive data)
        headers = {}
        for key, value in (request.headers or {}).items():
            if isinstance(value, list):
                value = value[0] if value else ""
            headers[key] = _sanitize_header(key, str(value))

        return cls(
            timestamp=timestamp.isoformat() + "Z",
            method=case.method,
            url=url,
            path=case.path,
            path_parameters=dict(case.path_parameters) if case.path_parameters else {},
            query_parameters=dict(case.query) if case.query else {},
            headers=headers,
            body=body,
            body_size=body_size,
        )


@dataclass
class ResponseData:
    """Captured HTTP response data."""

    status_code: int
    status_text: str
    headers: dict[str, str]
    body: Any
    body_size: int | None
    response_time_ms: float

    @classmethod
    def from_response(cls, response: Any) -> ResponseData:
        """Create ResponseData from a Response object."""
        # Get headers as dict
        headers = {}
        for key, value in (response.headers or {}).items():
            if isinstance(value, list):
                value = ", ".join(value)
            headers[key] = str(value)

        # Try to parse body as JSON
        body = None
        try:
            body = response.json()
        except Exception:
            try:
                body = response.text
            except Exception:
                if response.content:
                    body = f"<binary data: {len(response.content)} bytes>"

        body_size = response.body_size

        return cls(
            status_code=response.status_code,
            status_text=response.message or "",
            headers=headers,
            body=body,
            body_size=body_size,
            response_time_ms=response.elapsed * 1000,  # Convert to milliseconds
        )


@dataclass
class CheckResult:
    """Result of a single check execution."""

    name: str
    status: TestStatus
    message: str | None = None


@dataclass
class TestCaseResult:
    """Complete result of a single test case execution."""

    test_id: str
    operation_id: str | None
    tags: list[str]
    test_phase: str
    status: TestStatus
    request: RequestData
    response: ResponseData
    check_results: list[CheckResult]
    failure_reason: str | None
    curl_command: str | None

    @classmethod
    def create(
        cls,
        case: Any,
        response: Any,
        phase: str,
        check_results: list[CheckResult],
        failure_reason: str | None = None,
    ) -> TestCaseResult:
        """Create a TestCaseResult from case and response."""
        # Determine overall status
        if failure_reason:
            status = TestStatus.FAILED
        elif any(cr.status == TestStatus.FAILED for cr in check_results):
            status = TestStatus.FAILED
        elif any(cr.status == TestStatus.ERRORED for cr in check_results):
            status = TestStatus.ERRORED
        else:
            status = TestStatus.PASSED

        # Get operation metadata
        operation = case.operation
        operation_id = getattr(operation, "operation_id", None) or getattr(operation, "label", None)
        tags = list(getattr(operation, "tags", []) or [])

        # Generate curl command
        try:
            curl_command = case.as_curl_command()
        except Exception:
            curl_command = None

        return cls(
            test_id=str(uuid.uuid4()),
            operation_id=operation_id,
            tags=tags,
            test_phase=phase,
            status=status,
            request=RequestData.from_case_and_response(case, response),
            response=ResponseData.from_response(response),
            check_results=check_results,
            failure_reason=failure_reason,
            curl_command=curl_command,
        )


@dataclass
class EndpointSummary:
    """Aggregated statistics for a single endpoint."""

    method: str
    path: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    _response_times: list[float] = field(default_factory=list)

    def add_result(self, result: TestCaseResult) -> None:
        """Add a test result to this endpoint's statistics."""
        self.total_tests += 1

        if result.status == TestStatus.PASSED:
            self.passed += 1
        elif result.status == TestStatus.FAILED:
            self.failed += 1
        elif result.status == TestStatus.ERRORED:
            self.errored += 1
        elif result.status == TestStatus.SKIPPED:
            self.skipped += 1

        # Track response times
        response_time = result.response.response_time_ms
        self._response_times.append(response_time)

        # Update statistics
        if self._response_times:
            self.avg_response_time_ms = sum(self._response_times) / len(self._response_times)
            self.min_response_time_ms = min(self._response_times)
            self.max_response_time_ms = max(self._response_times)


@dataclass
class TestRunInfo:
    """Overall test run metadata and results."""

    run_id: str
    start_time: str
    end_time: str | None
    duration_seconds: float
    api_name: str
    api_version: str
    base_url: str
    total_tests: int
    passed: int
    failed: int
    errored: int
    skipped: int
    endpoints: dict[str, EndpointSummary]
    test_results: list[TestCaseResult]
    schemathesis_version: str

    @classmethod
    def create(cls, api_name: str = "", api_version: str = "", base_url: str = "") -> TestRunInfo:
        """Create a new TestRunInfo for a test run."""
        from schemathesis.core.version import SCHEMATHESIS_VERSION

        return cls(
            run_id=str(uuid.uuid4()),
            start_time=datetime.utcnow().isoformat() + "Z",
            end_time=None,
            duration_seconds=0.0,
            api_name=api_name,
            api_version=api_version,
            base_url=base_url,
            total_tests=0,
            passed=0,
            failed=0,
            errored=0,
            skipped=0,
            endpoints={},
            test_results=[],
            schemathesis_version=SCHEMATHESIS_VERSION,
        )

    def add_result(self, result: TestCaseResult) -> None:
        """Add a test result to the run."""
        self.test_results.append(result)
        self.total_tests += 1

        if result.status == TestStatus.PASSED:
            self.passed += 1
        elif result.status == TestStatus.FAILED:
            self.failed += 1
        elif result.status == TestStatus.ERRORED:
            self.errored += 1
        elif result.status == TestStatus.SKIPPED:
            self.skipped += 1

        # Update endpoint summary
        endpoint_key = f"{result.request.method} {result.request.path}"
        if endpoint_key not in self.endpoints:
            self.endpoints[endpoint_key] = EndpointSummary(
                method=result.request.method,
                path=result.request.path,
            )
        self.endpoints[endpoint_key].add_result(result)

    def finish(self) -> None:
        """Mark the test run as finished."""
        from datetime import datetime

        self.end_time = datetime.utcnow().isoformat() + "Z"
        if self.start_time and self.end_time:
            start = datetime.fromisoformat(self.start_time.rstrip("Z"))
            end = datetime.fromisoformat(self.end_time.rstrip("Z"))
            self.duration_seconds = (end - start).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "api_name": self.api_name,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "errored": self.errored,
            "skipped": self.skipped,
            "schemathesis_version": self.schemathesis_version,
            "endpoints": {
                key: {
                    "method": ep.method,
                    "path": ep.path,
                    "total_tests": ep.total_tests,
                    "passed": ep.passed,
                    "failed": ep.failed,
                    "errored": ep.errored,
                    "skipped": ep.skipped,
                    "avg_response_time_ms": round(ep.avg_response_time_ms, 2),
                    "min_response_time_ms": round(ep.min_response_time_ms, 2),
                    "max_response_time_ms": round(ep.max_response_time_ms, 2),
                }
                for key, ep in self.endpoints.items()
            },
            "test_results": [
                {
                    "test_id": tr.test_id,
                    "operation_id": tr.operation_id,
                    "tags": tr.tags,
                    "test_phase": tr.test_phase,
                    "status": tr.status.value,
                    "request": {
                        "timestamp": tr.request.timestamp,
                        "method": tr.request.method,
                        "url": tr.request.url,
                        "path": tr.request.path,
                        "path_parameters": tr.request.path_parameters,
                        "query_parameters": tr.request.query_parameters,
                        "headers": tr.request.headers,
                        "body": _serialize_body(tr.request.body),
                        "body_size": tr.request.body_size,
                    },
                    "response": {
                        "status_code": tr.response.status_code,
                        "status_text": tr.response.status_text,
                        "headers": tr.response.headers,
                        "body": _serialize_body(tr.response.body),
                        "body_size": tr.response.body_size,
                        "response_time_ms": round(tr.response.response_time_ms, 2),
                    },
                    "check_results": [
                        {
                            "name": cr.name,
                            "status": cr.status.value,
                            "message": cr.message,
                        }
                        for cr in tr.check_results
                    ],
                    "failure_reason": tr.failure_reason,
                    "curl_command": tr.curl_command,
                }
                for tr in self.test_results
            ],
        }


# Headers to sanitize (redact values)
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "x-auth-token",
    "cookie",
    "set-cookie",
    "x-csrf-token",
    "x-access-token",
}


def _sanitize_header(name: str, value: str) -> str:
    """Sanitize sensitive header values."""
    if name.lower() in SENSITIVE_HEADERS:
        return "[REDACTED]"
    return value


def _serialize_body(body: Any) -> Any:
    """Serialize body for JSON output, handling special types."""
    if body is None:
        return None
    if isinstance(body, bytes):
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            import base64
            return f"<base64:{base64.b64encode(body).decode()}>"
    if isinstance(body, (dict, list, str, int, float, bool)):
        return body
    return str(body)

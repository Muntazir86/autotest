"""Tests for autotest.reporting.models module."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from autotest.reporting.models import (
    CheckResult,
    EndpointSummary,
    RequestData,
    ResponseData,
    TestCaseResult,
    TestRunInfo,
    TestStatus,
    _sanitize_header,
    _serialize_body,
    SENSITIVE_HEADERS,
)
from autotest.core import NOT_SET


class TestTestStatus:
    """Tests for TestStatus enum."""

    def test_status_values(self):
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.ERRORED.value == "errored"
        assert TestStatus.SKIPPED.value == "skipped"

    def test_status_is_string_enum(self):
        assert isinstance(TestStatus.PASSED, str)
        assert TestStatus.PASSED == "passed"


class TestRequestData:
    """Tests for RequestData dataclass."""

    def test_basic_creation(self):
        request = RequestData(
            timestamp="2024-01-01T00:00:00Z",
            method="GET",
            url="http://example.com/api/test",
            path="/api/test",
            path_parameters={},
            query_parameters={"q": "search"},
            headers={"Content-Type": "application/json"},
            body=None,
            body_size=None,
        )
        assert request.method == "GET"
        assert request.url == "http://example.com/api/test"
        assert request.path == "/api/test"
        assert request.query_parameters == {"q": "search"}

    def test_from_case_and_response(self):
        mock_case = MagicMock()
        mock_case.method = "POST"
        mock_case.path = "/api/users"
        mock_case.body = {"name": "test"}
        mock_case.path_parameters = {"id": "123"}
        mock_case.query = {"page": "1"}

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/users"
        mock_response.request.headers = {"Content-Type": "application/json"}

        request_data = RequestData.from_case_and_response(mock_case, mock_response)

        assert request_data.method == "POST"
        assert request_data.path == "/api/users"
        assert request_data.body == {"name": "test"}
        assert request_data.path_parameters == {"id": "123"}
        assert request_data.query_parameters == {"page": "1"}

    def test_from_case_and_response_with_string_body(self):
        mock_case = MagicMock()
        mock_case.method = "POST"
        mock_case.path = "/api/data"
        mock_case.body = "test body content"
        mock_case.path_parameters = None
        mock_case.query = None

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/data"
        mock_response.request.headers = {}

        request_data = RequestData.from_case_and_response(mock_case, mock_response)

        assert request_data.body == "test body content"
        assert request_data.body_size == 17

    def test_from_case_and_response_sanitizes_headers(self):
        mock_case = MagicMock()
        mock_case.method = "GET"
        mock_case.path = "/api/secure"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/secure"
        mock_response.request.headers = {
            "Authorization": "Bearer secret-token",
            "Content-Type": "application/json",
        }

        request_data = RequestData.from_case_and_response(mock_case, mock_response)

        assert request_data.headers["Authorization"] == "[REDACTED]"
        assert request_data.headers["Content-Type"] == "application/json"


class TestResponseData:
    """Tests for ResponseData dataclass."""

    def test_basic_creation(self):
        response = ResponseData(
            status_code=200,
            status_text="OK",
            headers={"Content-Type": "application/json"},
            body={"result": "success"},
            body_size=20,
            response_time_ms=150.5,
        )
        assert response.status_code == 200
        assert response.status_text == "OK"
        assert response.response_time_ms == 150.5

    def test_from_response_json_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.message = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": "test"}
        mock_response.body_size = 15
        mock_response.elapsed = 0.1

        response_data = ResponseData.from_response(mock_response)

        assert response_data.status_code == 200
        assert response_data.status_text == "OK"
        assert response_data.body == {"data": "test"}
        assert response_data.response_time_ms == 100.0

    def test_from_response_text_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.message = "OK"
        mock_response.headers = {}
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = "Plain text response"
        mock_response.body_size = 19
        mock_response.elapsed = 0.05

        response_data = ResponseData.from_response(mock_response)

        assert response_data.body == "Plain text response"

    def test_from_response_binary_body(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.message = "OK"
        mock_response.headers = {}
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.text = property(lambda self: (_ for _ in ()).throw(Exception("Binary")))
        type(mock_response).text = property(lambda self: (_ for _ in ()).throw(Exception("Binary")))
        mock_response.content = b"\x00\x01\x02\x03"
        mock_response.body_size = 4
        mock_response.elapsed = 0.02

        response_data = ResponseData.from_response(mock_response)

        assert "<binary data: 4 bytes>" in response_data.body


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_passed_check(self):
        check = CheckResult(
            name="status_code_conformance",
            status=TestStatus.PASSED,
            message=None,
        )
        assert check.name == "status_code_conformance"
        assert check.status == TestStatus.PASSED
        assert check.message is None

    def test_failed_check(self):
        check = CheckResult(
            name="not_a_server_error",
            status=TestStatus.FAILED,
            message="Server returned 500",
        )
        assert check.status == TestStatus.FAILED
        assert check.message == "Server returned 500"


class TestTestCaseResult:
    """Tests for TestCaseResult dataclass."""

    def test_create_passed_result(self):
        mock_case = MagicMock()
        mock_case.method = "GET"
        mock_case.path = "/api/test"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = "getTest"
        mock_case.operation.tags = ["test"]
        mock_case.as_curl_command.return_value = "curl -X GET http://example.com/api/test"

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/test"
        mock_response.request.headers = {}
        mock_response.status_code = 200
        mock_response.message = "OK"
        mock_response.headers = {}
        mock_response.json.return_value = {"result": "ok"}
        mock_response.body_size = 15
        mock_response.elapsed = 0.1

        check_results = [
            CheckResult(name="not_a_server_error", status=TestStatus.PASSED, message=None),
        ]

        result = TestCaseResult.create(
            case=mock_case,
            response=mock_response,
            phase="positive",
            check_results=check_results,
        )

        assert result.status == TestStatus.PASSED
        assert result.operation_id == "getTest"
        assert result.tags == ["test"]
        assert result.test_phase == "positive"

    def test_create_failed_result_with_failure_reason(self):
        mock_case = MagicMock()
        mock_case.method = "POST"
        mock_case.path = "/api/fail"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = None
        mock_case.operation.label = "postFail"
        mock_case.operation.tags = None
        mock_case.as_curl_command.return_value = "curl -X POST http://example.com/api/fail"

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/fail"
        mock_response.request.headers = {}
        mock_response.status_code = 500
        mock_response.message = "Internal Server Error"
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "failed"}
        mock_response.body_size = 18
        mock_response.elapsed = 0.2

        check_results = [
            CheckResult(name="not_a_server_error", status=TestStatus.PASSED, message=None),
        ]

        result = TestCaseResult.create(
            case=mock_case,
            response=mock_response,
            phase="negative",
            check_results=check_results,
            failure_reason="Server error",
        )

        assert result.status == TestStatus.FAILED
        assert result.failure_reason == "Server error"

    def test_create_result_with_failed_check(self):
        mock_case = MagicMock()
        mock_case.method = "GET"
        mock_case.path = "/api/test"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = "test"
        mock_case.operation.tags = []
        mock_case.as_curl_command.side_effect = Exception("Cannot generate curl")

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/test"
        mock_response.request.headers = {}
        mock_response.status_code = 500
        mock_response.message = "Error"
        mock_response.headers = {}
        mock_response.json.return_value = {}
        mock_response.body_size = 2
        mock_response.elapsed = 0.1

        check_results = [
            CheckResult(name="not_a_server_error", status=TestStatus.FAILED, message="Server error"),
        ]

        result = TestCaseResult.create(
            case=mock_case,
            response=mock_response,
            phase="positive",
            check_results=check_results,
        )

        assert result.status == TestStatus.FAILED
        assert result.curl_command is None


class TestEndpointSummary:
    """Tests for EndpointSummary dataclass."""

    def test_initial_state(self):
        summary = EndpointSummary(method="GET", path="/api/test")
        assert summary.total_tests == 0
        assert summary.passed == 0
        assert summary.failed == 0
        assert summary.avg_response_time_ms == 0.0

    def test_add_passed_result(self):
        summary = EndpointSummary(method="GET", path="/api/test")

        mock_result = MagicMock()
        mock_result.status = TestStatus.PASSED
        mock_result.response.response_time_ms = 100.0

        summary.add_result(mock_result)

        assert summary.total_tests == 1
        assert summary.passed == 1
        assert summary.failed == 0
        assert summary.avg_response_time_ms == 100.0

    def test_add_failed_result(self):
        summary = EndpointSummary(method="POST", path="/api/create")

        mock_result = MagicMock()
        mock_result.status = TestStatus.FAILED
        mock_result.response.response_time_ms = 200.0

        summary.add_result(mock_result)

        assert summary.total_tests == 1
        assert summary.passed == 0
        assert summary.failed == 1

    def test_add_multiple_results(self):
        summary = EndpointSummary(method="GET", path="/api/test")

        for i, status in enumerate([TestStatus.PASSED, TestStatus.PASSED, TestStatus.FAILED]):
            mock_result = MagicMock()
            mock_result.status = status
            mock_result.response.response_time_ms = (i + 1) * 100.0
            summary.add_result(mock_result)

        assert summary.total_tests == 3
        assert summary.passed == 2
        assert summary.failed == 1
        assert summary.avg_response_time_ms == 200.0
        assert summary.min_response_time_ms == 100.0
        assert summary.max_response_time_ms == 300.0

    def test_add_errored_and_skipped_results(self):
        summary = EndpointSummary(method="GET", path="/api/test")

        mock_errored = MagicMock()
        mock_errored.status = TestStatus.ERRORED
        mock_errored.response.response_time_ms = 50.0

        mock_skipped = MagicMock()
        mock_skipped.status = TestStatus.SKIPPED
        mock_skipped.response.response_time_ms = 0.0

        summary.add_result(mock_errored)
        summary.add_result(mock_skipped)

        assert summary.total_tests == 2
        assert summary.errored == 1
        assert summary.skipped == 1


class TestTestRunInfo:
    """Tests for TestRunInfo dataclass."""

    def test_create(self):
        run_info = TestRunInfo.create(
            api_name="Test API",
            api_version="v1",
            base_url="http://example.com",
        )

        assert run_info.api_name == "Test API"
        assert run_info.api_version == "v1"
        assert run_info.base_url == "http://example.com"
        assert run_info.total_tests == 0
        assert run_info.passed == 0
        assert run_info.failed == 0
        assert run_info.end_time is None

    def test_add_result(self):
        run_info = TestRunInfo.create()

        mock_result = MagicMock()
        mock_result.status = TestStatus.PASSED
        mock_result.request.method = "GET"
        mock_result.request.path = "/api/test"
        mock_result.response.response_time_ms = 100.0

        run_info.add_result(mock_result)

        assert run_info.total_tests == 1
        assert run_info.passed == 1
        assert len(run_info.test_results) == 1
        assert "GET /api/test" in run_info.endpoints

    def test_add_multiple_results_same_endpoint(self):
        run_info = TestRunInfo.create()

        for status in [TestStatus.PASSED, TestStatus.FAILED]:
            mock_result = MagicMock()
            mock_result.status = status
            mock_result.request.method = "GET"
            mock_result.request.path = "/api/test"
            mock_result.response.response_time_ms = 100.0
            run_info.add_result(mock_result)

        assert run_info.total_tests == 2
        assert run_info.passed == 1
        assert run_info.failed == 1
        assert len(run_info.endpoints) == 1
        assert run_info.endpoints["GET /api/test"].total_tests == 2

    def test_finish(self):
        run_info = TestRunInfo.create()

        run_info.finish()

        assert run_info.end_time is not None
        assert run_info.duration_seconds >= 0

    def test_to_dict(self):
        run_info = TestRunInfo.create(
            api_name="Test API",
            api_version="v1",
            base_url="http://example.com",
        )

        run_info.finish()
        data = run_info.to_dict()

        assert data["api_name"] == "Test API"
        assert data["api_version"] == "v1"
        assert data["base_url"] == "http://example.com"
        assert data["total_tests"] == 0
        assert "endpoints" in data
        assert "test_results" in data


class TestSanitizeHeader:
    """Tests for _sanitize_header function."""

    def test_sanitizes_authorization(self):
        assert _sanitize_header("Authorization", "Bearer token") == "[REDACTED]"
        assert _sanitize_header("authorization", "Basic creds") == "[REDACTED]"

    def test_sanitizes_api_key(self):
        assert _sanitize_header("X-API-Key", "secret-key") == "[REDACTED]"
        assert _sanitize_header("api-key", "secret") == "[REDACTED]"

    def test_sanitizes_cookie(self):
        assert _sanitize_header("Cookie", "session=abc123") == "[REDACTED]"
        assert _sanitize_header("Set-Cookie", "session=xyz") == "[REDACTED]"

    def test_does_not_sanitize_normal_headers(self):
        assert _sanitize_header("Content-Type", "application/json") == "application/json"
        assert _sanitize_header("Accept", "*/*") == "*/*"

    def test_all_sensitive_headers(self):
        for header in SENSITIVE_HEADERS:
            assert _sanitize_header(header, "value") == "[REDACTED]"


class TestSerializeBody:
    """Tests for _serialize_body function."""

    def test_serialize_none(self):
        assert _serialize_body(None) is None

    def test_serialize_dict(self):
        assert _serialize_body({"key": "value"}) == {"key": "value"}

    def test_serialize_list(self):
        assert _serialize_body([1, 2, 3]) == [1, 2, 3]

    def test_serialize_string(self):
        assert _serialize_body("test string") == "test string"

    def test_serialize_bytes_utf8(self):
        assert _serialize_body(b"hello world") == "hello world"

    def test_serialize_bytes_binary(self):
        result = _serialize_body(b"\x00\x01\x02\x03")
        assert "base64" in result or result == b"\x00\x01\x02\x03".decode("latin-1")

    def test_serialize_other_types(self):
        class CustomObj:
            def __str__(self):
                return "custom object"

        assert _serialize_body(CustomObj()) == "custom object"

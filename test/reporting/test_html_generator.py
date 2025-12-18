"""Tests for autotest.reporting.html_generator module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from autotest.reporting.html_generator import HTMLReportGenerator
from autotest.reporting.models import (
    CheckResult,
    EndpointSummary,
    RequestData,
    ResponseData,
    TestCaseResult,
    TestRunInfo,
    TestStatus,
)


@pytest.fixture
def sample_run_info():
    """Create a sample TestRunInfo for testing."""
    run_info = TestRunInfo.create(
        api_name="Test API",
        api_version="v1",
        base_url="http://example.com",
    )

    request_data = RequestData(
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

    response_data = ResponseData(
        status_code=200,
        status_text="OK",
        headers={"Content-Type": "application/json"},
        body={"result": "success"},
        body_size=20,
        response_time_ms=150.5,
    )

    test_result = TestCaseResult(
        test_id="test-123",
        operation_id="getTest",
        tags=["test"],
        test_phase="positive",
        status=TestStatus.PASSED,
        request=request_data,
        response=response_data,
        check_results=[
            CheckResult(name="not_a_server_error", status=TestStatus.PASSED, message=None),
        ],
        failure_reason=None,
        curl_command="curl -X GET http://example.com/api/test",
    )

    run_info.test_results.append(test_result)
    run_info.total_tests = 1
    run_info.passed = 1
    run_info.endpoints["GET /api/test"] = EndpointSummary(
        method="GET",
        path="/api/test",
        total_tests=1,
        passed=1,
        failed=0,
        errored=0,
        skipped=0,
        avg_response_time_ms=150.5,
        min_response_time_ms=150.5,
        max_response_time_ms=150.5,
    )
    run_info.finish()

    return run_info


@pytest.fixture
def sample_run_info_with_failures():
    """Create a sample TestRunInfo with failures for testing."""
    run_info = TestRunInfo.create(
        api_name="Test API",
        api_version="v1",
        base_url="http://example.com",
    )

    request_data = RequestData(
        timestamp="2024-01-01T00:00:00Z",
        method="POST",
        url="http://example.com/api/fail",
        path="/api/fail",
        path_parameters={},
        query_parameters={},
        headers={"Content-Type": "application/json"},
        body={"data": "test"},
        body_size=15,
    )

    response_data = ResponseData(
        status_code=500,
        status_text="Internal Server Error",
        headers={"Content-Type": "application/json"},
        body={"error": "Something went wrong"},
        body_size=30,
        response_time_ms=250.0,
    )

    test_result = TestCaseResult(
        test_id="test-456",
        operation_id="postFail",
        tags=["fail"],
        test_phase="negative",
        status=TestStatus.FAILED,
        request=request_data,
        response=response_data,
        check_results=[
            CheckResult(name="not_a_server_error", status=TestStatus.FAILED, message="Server returned 500"),
        ],
        failure_reason="Server error: 500",
        curl_command="curl -X POST http://example.com/api/fail -d '{\"data\":\"test\"}'",
    )

    run_info.test_results.append(test_result)
    run_info.total_tests = 1
    run_info.failed = 1
    run_info.endpoints["POST /api/fail"] = EndpointSummary(
        method="POST",
        path="/api/fail",
        total_tests=1,
        passed=0,
        failed=1,
        errored=0,
        skipped=0,
        avg_response_time_ms=250.0,
        min_response_time_ms=250.0,
        max_response_time_ms=250.0,
    )
    run_info.finish()

    return run_info


class TestHTMLReportGenerator:
    """Tests for HTMLReportGenerator class."""

    def test_initialization_defaults(self):
        generator = HTMLReportGenerator()
        assert generator.title == "API Test Report"
        assert generator.include_passed_details is False

    def test_initialization_with_params(self):
        generator = HTMLReportGenerator(
            title="Custom Report",
            include_passed_details=True,
        )
        assert generator.title == "Custom Report"
        assert generator.include_passed_details is True

    def test_generate_creates_file(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator(title="Test Report")
        output_path = tmp_path / "report.html"

        result = generator.generate(sample_run_info, output_path)

        assert result == output_path
        assert output_path.exists()

    def test_generate_creates_parent_directories(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "nested" / "dir" / "report.html"

        result = generator.generate(sample_run_info, output_path)

        assert result == output_path
        assert output_path.exists()

    def test_generate_html_contains_title(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator(title="My Custom Title")
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "My Custom Title" in content

    def test_generate_html_contains_api_info(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "Test API" in content
        assert "v1" in content
        assert "http://example.com" in content

    def test_generate_html_contains_summary_stats(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "Total Tests" in content
        assert "Passed" in content
        assert "Failed" in content

    def test_generate_html_contains_endpoints_table(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "Endpoints Overview" in content
        assert "/api/test" in content
        assert "GET" in content

    def test_generate_html_contains_all_tests_section(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "All Tests" in content
        assert "searchInput" in content
        assert "statusFilter" in content

    def test_generate_html_contains_failed_tests_section(self, tmp_path, sample_run_info_with_failures):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info_with_failures, output_path)

        content = output_path.read_text()
        assert "Failed Tests" in content
        assert "Server error: 500" in content
        assert "/api/fail" in content

    def test_generate_html_contains_curl_command(self, tmp_path, sample_run_info_with_failures):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info_with_failures, output_path)

        content = output_path.read_text()
        assert "cURL Command" in content
        assert "curl -X POST" in content

    def test_generate_html_contains_check_results(self, tmp_path, sample_run_info_with_failures):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info_with_failures, output_path)

        content = output_path.read_text()
        assert "Check Results" in content
        assert "not_a_server_error" in content

    def test_generate_html_contains_javascript(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "toggleDetails" in content
        assert "copyToClipboard" in content
        assert "filterTests" in content

    def test_generate_html_contains_css(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "<style>" in content
        assert ".container" in content
        assert ".summary-card" in content

    def test_generate_html_is_valid_html(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "<head>" in content
        assert "</head>" in content
        assert "<body>" in content
        assert "</body>" in content

    def test_generate_html_embeds_json_data(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "const reportData =" in content

    def test_generate_html_no_failures_message(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(sample_run_info, output_path)

        content = output_path.read_text()
        assert "No failures" in content or "All tests passed" in content


class TestHTMLReportGeneratorHelperMethods:
    """Tests for HTMLReportGenerator helper methods."""

    def test_format_json_none(self):
        generator = HTMLReportGenerator()
        assert generator._format_json(None) == "null"

    def test_format_json_dict(self):
        generator = HTMLReportGenerator()
        result = generator._format_json({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_format_json_string_valid_json(self):
        generator = HTMLReportGenerator()
        result = generator._format_json('{"key": "value"}')
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_format_json_string_invalid_json(self):
        generator = HTMLReportGenerator()
        result = generator._format_json("not json")
        assert result == "not json"

    def test_escape_js_backticks(self):
        generator = HTMLReportGenerator()
        result = generator._escape_js("test `backtick` string")
        assert "\\`" in result

    def test_escape_js_backslashes(self):
        generator = HTMLReportGenerator()
        result = generator._escape_js("test\\path")
        assert "\\\\" in result

    def test_escape_js_dollar_signs(self):
        generator = HTMLReportGenerator()
        result = generator._escape_js("test $variable")
        assert "\\$" in result

    def test_generate_endpoint_rows_empty(self):
        generator = HTMLReportGenerator()
        result = generator._generate_endpoint_rows({})
        assert "No endpoints tested" in result

    def test_generate_endpoint_rows_with_data(self):
        generator = HTMLReportGenerator()
        endpoints = {
            "GET /api/test": {
                "method": "GET",
                "path": "/api/test",
                "total_tests": 5,
                "passed": 4,
                "failed": 1,
                "avg_response_time_ms": 100.5,
            }
        }
        result = generator._generate_endpoint_rows(endpoints)
        assert "GET" in result
        assert "/api/test" in result
        assert "5" in result
        assert "4" in result
        assert "1" in result

    def test_generate_failed_tests_empty(self):
        generator = HTMLReportGenerator()
        result = generator._generate_failed_tests([])
        assert result == ""

    def test_generate_failed_tests_with_failures(self):
        generator = HTMLReportGenerator()
        test_results = [
            {
                "status": "failed",
                "request": {
                    "method": "POST",
                    "url": "http://example.com/api/fail",
                    "path": "/api/fail",
                    "headers": {"Content-Type": "application/json"},
                    "body": None,
                },
                "response": {
                    "status_code": 500,
                    "status_text": "Error",
                    "headers": {"Content-Type": "application/json"},
                    "body": None,
                    "response_time_ms": 100.0,
                },
                "check_results": [
                    {"name": "check1", "status": "failed", "message": "Error message"},
                ],
                "failure_reason": "Server error",
                "curl_command": "curl -X POST http://example.com/api/fail",
            }
        ]
        result = generator._generate_failed_tests(test_results)
        assert "POST" in result
        assert "/api/fail" in result
        assert "Server error" in result
        assert "curl -X POST" in result

    def test_generate_all_tests_empty(self):
        generator = HTMLReportGenerator()
        result = generator._generate_all_tests([])
        assert "No tests recorded" in result

    def test_generate_all_tests_with_data(self):
        generator = HTMLReportGenerator()
        test_results = [
            {
                "status": "passed",
                "request": {
                    "method": "GET",
                    "url": "http://example.com/api/test",
                    "path": "/api/test",
                },
                "response": {
                    "status_code": 200,
                    "response_time_ms": 50.0,
                },
                "test_phase": "positive",
                "operation_id": "getTest",
            }
        ]
        result = generator._generate_all_tests(test_results)
        assert "GET" in result
        assert "/api/test" in result
        assert "passed" in result
        assert "200" in result


class TestHTMLReportGeneratorEdgeCases:
    """Edge case tests for HTMLReportGenerator."""

    def test_generate_with_string_path(self, tmp_path, sample_run_info):
        generator = HTMLReportGenerator()
        output_path = str(tmp_path / "report.html")

        result = generator.generate(sample_run_info, output_path)

        assert result == Path(output_path)
        assert Path(output_path).exists()

    def test_generate_with_zero_tests(self, tmp_path):
        run_info = TestRunInfo.create()
        run_info.finish()

        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(run_info, output_path)

        content = output_path.read_text()
        assert "0" in content
        assert "Total Tests" in content

    def test_generate_with_special_characters_in_body(self, tmp_path):
        run_info = TestRunInfo.create()

        request_data = RequestData(
            timestamp="2024-01-01T00:00:00Z",
            method="POST",
            url="http://example.com/api/test",
            path="/api/test",
            path_parameters={},
            query_parameters={},
            headers={},
            body='{"message": "<script>alert(\'xss\')</script>"}',
            body_size=50,
        )

        response_data = ResponseData(
            status_code=200,
            status_text="OK",
            headers={},
            body={"result": "success"},
            body_size=20,
            response_time_ms=100.0,
        )

        test_result = TestCaseResult(
            test_id="test-special",
            operation_id="test",
            tags=[],
            test_phase="positive",
            status=TestStatus.PASSED,
            request=request_data,
            response=response_data,
            check_results=[],
            failure_reason=None,
            curl_command=None,
        )

        run_info.test_results.append(test_result)
        run_info.total_tests = 1
        run_info.passed = 1
        run_info.finish()

        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(run_info, output_path)

        assert output_path.exists()

    def test_generate_with_all_http_methods(self, tmp_path):
        run_info = TestRunInfo.create()

        methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        for method in methods:
            run_info.endpoints[f"{method} /api/test"] = EndpointSummary(
                method=method,
                path="/api/test",
                total_tests=1,
                passed=1,
            )

        run_info.finish()

        generator = HTMLReportGenerator()
        output_path = tmp_path / "report.html"

        generator.generate(run_info, output_path)

        content = output_path.read_text()
        for method in methods:
            assert f"method-{method.lower()}" in content

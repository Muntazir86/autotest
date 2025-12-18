"""Tests for autotest.reporting.hooks module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from autotest.reporting.hooks import (
    _after_call_hook,
    disable_html_report,
    enable_html_report,
    generate_report,
    get_collection_summary,
    is_enabled,
    set_phase,
)
from autotest.reporting.collector import get_collector, set_collector


class TestEnableDisableHtmlReport:
    """Tests for enable_html_report and disable_html_report functions."""

    def teardown_method(self):
        disable_html_report()

    def test_enable_html_report_basic(self, tmp_path):
        output_path = tmp_path / "report.html"

        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(output_path)

        assert is_enabled() is True
        collector = get_collector()
        assert collector is not None

    def test_enable_html_report_with_all_params(self, tmp_path):
        output_path = tmp_path / "report.html"

        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(
                output_path=output_path,
                title="Custom Report Title",
                include_passed_details=True,
                max_body_size=5000,
                sanitize_headers=["X-Custom-Header"],
                api_name="Test API",
                api_version="v2",
                base_url="http://example.com",
            )

        assert is_enabled() is True
        collector = get_collector()
        assert collector is not None
        assert collector.run_info.api_name == "Test API"
        assert collector.run_info.api_version == "v2"
        assert collector.run_info.base_url == "http://example.com"

    def test_disable_html_report(self, tmp_path):
        output_path = tmp_path / "report.html"

        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(output_path)

        assert is_enabled() is True

        with patch("autotest.reporting.hooks._unregister_hooks"):
            disable_html_report()

        assert is_enabled() is False
        assert get_collector() is None


class TestIsEnabled:
    """Tests for is_enabled function."""

    def teardown_method(self):
        disable_html_report()

    def test_is_enabled_false_by_default(self):
        with patch("autotest.reporting.hooks._unregister_hooks"):
            disable_html_report()
        assert is_enabled() is False

    def test_is_enabled_true_after_enable(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")
        assert is_enabled() is True


class TestGenerateReport:
    """Tests for generate_report function."""

    def teardown_method(self):
        disable_html_report()

    def test_generate_report_when_not_enabled(self):
        with patch("autotest.reporting.hooks._unregister_hooks"):
            disable_html_report()
        result = generate_report()
        assert result is None

    def test_generate_report_when_enabled(self, tmp_path):
        output_path = tmp_path / "report.html"

        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(
                output_path=output_path,
                title="Test Report",
                api_name="Test API",
            )

        result = generate_report()

        assert result is not None
        assert result == output_path
        assert output_path.exists()

        content = output_path.read_text()
        assert "Test Report" in content
        assert "Test API" in content

    def test_generate_report_creates_parent_directories(self, tmp_path):
        output_path = tmp_path / "nested" / "dir" / "report.html"

        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(output_path=output_path)

        result = generate_report()

        assert result is not None
        assert output_path.exists()


class TestSetPhase:
    """Tests for set_phase function."""

    def teardown_method(self):
        disable_html_report()

    def test_set_phase_when_no_collector(self):
        set_collector(None)
        set_phase("positive")

    def test_set_phase_when_collector_exists(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")

        set_phase("negative")

        collector = get_collector()
        assert collector._current_phase == "negative"


class TestGetCollectionSummary:
    """Tests for get_collection_summary function."""

    def teardown_method(self):
        disable_html_report()

    def test_get_collection_summary_when_no_collector(self):
        set_collector(None)
        result = get_collection_summary()
        assert result is None

    def test_get_collection_summary_when_collector_exists(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")

        summary = get_collection_summary()

        assert summary is not None
        assert "total" in summary
        assert "passed" in summary
        assert "failed" in summary
        assert "errored" in summary
        assert "skipped" in summary
        assert "endpoints_tested" in summary


class TestAfterCallHook:
    """Tests for _after_call_hook function."""

    def teardown_method(self):
        disable_html_report()

    def test_after_call_hook_when_not_enabled(self):
        with patch("autotest.reporting.hooks._unregister_hooks"):
            disable_html_report()

        mock_context = MagicMock()
        mock_case = MagicMock()
        mock_response = MagicMock()

        _after_call_hook(mock_context, mock_case, mock_response)

    def test_after_call_hook_when_no_collector(self):
        with patch("autotest.reporting.hooks._enabled", True):
            set_collector(None)

            mock_context = MagicMock()
            mock_case = MagicMock()
            mock_response = MagicMock()

            _after_call_hook(mock_context, mock_case, mock_response)

    def test_after_call_hook_records_test(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")

        mock_context = MagicMock()

        mock_case = MagicMock()
        mock_case.method = "GET"
        mock_case.path = "/api/test"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = "getTest"
        mock_case.operation.tags = []
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

        _after_call_hook(mock_context, mock_case, mock_response)

        collector = get_collector()
        assert collector.run_info.total_tests == 1

    def test_after_call_hook_records_server_error(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")

        mock_context = MagicMock()

        mock_case = MagicMock()
        mock_case.method = "POST"
        mock_case.path = "/api/fail"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = "postFail"
        mock_case.operation.tags = []
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

        _after_call_hook(mock_context, mock_case, mock_response)

        collector = get_collector()
        assert collector.run_info.total_tests == 1
        assert collector.run_info.failed == 1

    def test_after_call_hook_handles_exceptions_gracefully(self, tmp_path):
        with patch("autotest.reporting.hooks._register_hooks"):
            enable_html_report(tmp_path / "report.html")

        mock_context = MagicMock()
        mock_case = MagicMock()
        mock_case.method = "GET"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(get_collector(), "record_test", side_effect=Exception("Test error")):
            _after_call_hook(mock_context, mock_case, mock_response)

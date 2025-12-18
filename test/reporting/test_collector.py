"""Tests for autotest.reporting.collector module."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from autotest.reporting.collector import (
    DataCollector,
    collector_context,
    get_collector,
    set_collector,
)
from autotest.reporting.models import TestStatus


class TestCollectorStorage:
    """Tests for thread-local collector storage."""

    def test_get_collector_returns_none_by_default(self):
        set_collector(None)
        assert get_collector() is None

    def test_set_and_get_collector(self):
        collector = DataCollector()
        set_collector(collector)
        assert get_collector() is collector
        set_collector(None)

    def test_collector_is_thread_local(self):
        main_collector = DataCollector(api_name="main")
        set_collector(main_collector)

        thread_collector_value = [None]

        def thread_func():
            thread_collector_value[0] = get_collector()

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        assert get_collector() is main_collector
        assert thread_collector_value[0] is None
        set_collector(None)


class TestCollectorContext:
    """Tests for collector_context context manager."""

    def test_sets_collector_in_context(self):
        set_collector(None)
        collector = DataCollector()

        with collector_context(collector) as ctx:
            assert get_collector() is collector
            assert ctx is collector

        assert get_collector() is None

    def test_restores_previous_collector(self):
        original = DataCollector(api_name="original")
        new = DataCollector(api_name="new")
        set_collector(original)

        with collector_context(new):
            assert get_collector() is new

        assert get_collector() is original
        set_collector(None)

    def test_restores_on_exception(self):
        original = DataCollector(api_name="original")
        new = DataCollector(api_name="new")
        set_collector(original)

        with pytest.raises(ValueError):
            with collector_context(new):
                assert get_collector() is new
                raise ValueError("test error")

        assert get_collector() is original
        set_collector(None)


class TestDataCollector:
    """Tests for DataCollector class."""

    def test_initialization_defaults(self):
        collector = DataCollector()
        assert collector._max_body_size == 10240
        assert collector._include_passed_details is False
        assert collector._current_phase == "unknown"

    def test_initialization_with_params(self):
        collector = DataCollector(
            api_name="Test API",
            api_version="v2",
            base_url="http://example.com",
            max_body_size=5000,
            sanitize_headers=["X-Custom-Secret"],
            include_passed_details=True,
        )
        assert collector.run_info.api_name == "Test API"
        assert collector.run_info.api_version == "v2"
        assert collector.run_info.base_url == "http://example.com"
        assert collector._max_body_size == 5000
        assert "X-Custom-Secret" in collector._sanitize_headers
        assert collector._include_passed_details is True

    def test_run_info_property(self):
        collector = DataCollector(api_name="Test")
        assert collector.run_info is not None
        assert collector.run_info.api_name == "Test"

    def test_set_phase(self):
        collector = DataCollector()
        assert collector._current_phase == "unknown"

        collector.set_phase("positive")
        assert collector._current_phase == "positive"

        collector.set_phase("negative")
        assert collector._current_phase == "negative"

    def test_record_test(self):
        collector = DataCollector()
        collector.set_phase("positive")

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

        collector.record_test(
            case=mock_case,
            response=mock_response,
            check_results=[("not_a_server_error", True, None)],
        )

        assert collector.run_info.total_tests == 1
        assert collector.run_info.passed == 1
        assert len(collector.run_info.test_results) == 1

    def test_record_test_with_failure(self):
        collector = DataCollector()
        collector.set_phase("negative")

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

        collector.record_test(
            case=mock_case,
            response=mock_response,
            check_results=[("not_a_server_error", False, "Server returned 500")],
            failure_reason="Server error",
        )

        assert collector.run_info.total_tests == 1
        assert collector.run_info.failed == 1

    def test_truncate_body_request(self):
        collector = DataCollector(max_body_size=10)

        mock_result = MagicMock()
        mock_result.request.body = "This is a very long request body that should be truncated"
        mock_result.request.body_size = 57
        mock_result.response.body = "short"
        mock_result.response.body_size = 5

        collector._truncate_body(mock_result)

        assert "truncated" in mock_result.request.body
        assert mock_result.request.body.startswith("This is a ")

    def test_truncate_body_response(self):
        collector = DataCollector(max_body_size=10)

        mock_result = MagicMock()
        mock_result.request.body = "short"
        mock_result.request.body_size = 5
        mock_result.response.body = "This is a very long response body that should be truncated"
        mock_result.response.body_size = 58

        collector._truncate_body(mock_result)

        assert "truncated" in mock_result.response.body

    def test_finish(self):
        collector = DataCollector()
        run_info = collector.finish()

        assert run_info.end_time is not None
        assert run_info.duration_seconds >= 0

    def test_get_summary(self):
        collector = DataCollector()

        mock_case = MagicMock()
        mock_case.method = "GET"
        mock_case.path = "/api/test"
        mock_case.body = None
        mock_case.path_parameters = None
        mock_case.query = None
        mock_case.operation.operation_id = "test"
        mock_case.operation.tags = []
        mock_case.as_curl_command.return_value = "curl"

        mock_response = MagicMock()
        mock_response.request.url = "http://example.com/api/test"
        mock_response.request.headers = {}
        mock_response.status_code = 200
        mock_response.message = "OK"
        mock_response.headers = {}
        mock_response.json.return_value = {}
        mock_response.body_size = 2
        mock_response.elapsed = 0.1

        collector.record_test(
            case=mock_case,
            response=mock_response,
            check_results=[("check", True, None)],
        )

        summary = collector.get_summary()

        assert summary["total"] == 1
        assert summary["passed"] == 1
        assert summary["failed"] == 0
        assert summary["errored"] == 0
        assert summary["skipped"] == 0
        assert summary["endpoints_tested"] == 1

    def test_thread_safety(self):
        collector = DataCollector()
        results = []
        errors = []

        def record_tests(thread_id):
            try:
                for i in range(10):
                    mock_case = MagicMock()
                    mock_case.method = "GET"
                    mock_case.path = f"/api/test/{thread_id}/{i}"
                    mock_case.body = None
                    mock_case.path_parameters = None
                    mock_case.query = None
                    mock_case.operation.operation_id = f"test_{thread_id}_{i}"
                    mock_case.operation.tags = []
                    mock_case.as_curl_command.return_value = "curl"

                    mock_response = MagicMock()
                    mock_response.request.url = f"http://example.com/api/test/{thread_id}/{i}"
                    mock_response.request.headers = {}
                    mock_response.status_code = 200
                    mock_response.message = "OK"
                    mock_response.headers = {}
                    mock_response.json.return_value = {}
                    mock_response.body_size = 2
                    mock_response.elapsed = 0.01

                    collector.record_test(
                        case=mock_case,
                        response=mock_response,
                        check_results=[("check", True, None)],
                    )
                results.append(thread_id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_tests, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5
        assert collector.run_info.total_tests == 50

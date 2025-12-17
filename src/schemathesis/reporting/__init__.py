"""HTML Report Generator and Data Collection for Schemathesis.

This module provides:
- Data collection during test execution
- HTML report generation with interactive features
- Request/response data capture and formatting
"""

from __future__ import annotations

from schemathesis.reporting.collector import DataCollector, get_collector, set_collector
from schemathesis.reporting.html_generator import HTMLReportGenerator
from schemathesis.reporting.models import (
    CheckResult,
    EndpointSummary,
    RequestData,
    ResponseData,
    TestCaseResult,
    TestRunInfo,
)
from schemathesis.reporting.hooks import (
    enable_html_report,
    disable_html_report,
    generate_report,
    is_enabled,
)

__all__ = [
    "DataCollector",
    "get_collector",
    "set_collector",
    "HTMLReportGenerator",
    "TestRunInfo",
    "EndpointSummary",
    "TestCaseResult",
    "RequestData",
    "ResponseData",
    "CheckResult",
    "enable_html_report",
    "disable_html_report",
    "generate_report",
    "is_enabled",
]

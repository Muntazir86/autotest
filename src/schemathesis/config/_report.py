from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from schemathesis.config._diff_base import DiffBase
from schemathesis.config._env import resolve

DEFAULT_REPORT_DIRECTORY = Path("./schemathesis-report")


class ReportFormat(str, Enum):
    """Available report formats."""

    JUNIT = "junit"
    VCR = "vcr"
    HAR = "har"
    HTML = "html"

    @property
    def extension(self) -> str:
        """File extension for this format."""
        return {
            self.JUNIT: "xml",
            self.VCR: "yaml",
            self.HAR: "json",
            self.HTML: "html",
        }[self]


@dataclass(repr=False)
class ReportConfig(DiffBase):
    enabled: bool
    path: Path | None

    __slots__ = ("enabled", "path")

    def __init__(self, *, enabled: bool = False, path: Path | None = None) -> None:
        self.enabled = enabled
        self.path = path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportConfig:
        path = resolve(data.get("path"))
        if path is not None:
            return cls(enabled=True, path=Path(path))
        enabled = data.get("enabled", False)
        return cls(enabled=enabled, path=path)


@dataclass(repr=False)
class HTMLReportConfig(DiffBase):
    """Configuration for HTML report generation."""

    enabled: bool
    path: Path | None
    title: str
    include_passed_details: bool
    max_body_size: int
    sanitize_headers: list[str]

    __slots__ = ("enabled", "path", "title", "include_passed_details", "max_body_size", "sanitize_headers")

    def __init__(
        self,
        *,
        enabled: bool = False,
        path: Path | None = None,
        title: str = "API Test Report",
        include_passed_details: bool = False,
        max_body_size: int = 10240,
        sanitize_headers: list[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self.path = path
        self.title = title
        self.include_passed_details = include_passed_details
        self.max_body_size = max_body_size
        self.sanitize_headers = sanitize_headers or ["Authorization", "X-API-Key"]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HTMLReportConfig:
        path = resolve(data.get("path"))
        return cls(
            enabled=data.get("enabled", path is not None),
            path=Path(path) if path else None,
            title=data.get("title", "API Test Report"),
            include_passed_details=data.get("include-passed-details", False),
            max_body_size=data.get("max-body-size", 10240),
            sanitize_headers=data.get("sanitize-headers", ["Authorization", "X-API-Key"]),
        )


@dataclass(repr=False)
class ReportsConfig(DiffBase):
    directory: Path
    preserve_bytes: bool
    junit: ReportConfig
    vcr: ReportConfig
    har: ReportConfig
    html: HTMLReportConfig
    _timestamp: str

    __slots__ = ("directory", "preserve_bytes", "junit", "vcr", "har", "html", "_timestamp")

    def __init__(
        self,
        *,
        directory: str | None = None,
        preserve_bytes: bool = False,
        junit: ReportConfig | None = None,
        vcr: ReportConfig | None = None,
        har: ReportConfig | None = None,
        html: HTMLReportConfig | None = None,
    ) -> None:
        self.directory = Path(resolve(directory) or DEFAULT_REPORT_DIRECTORY)
        self.preserve_bytes = preserve_bytes
        self.junit = junit or ReportConfig()
        self.vcr = vcr or ReportConfig()
        self.har = har or ReportConfig()
        self.html = html or HTMLReportConfig()
        self._timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportsConfig:
        return cls(
            directory=data.get("directory"),
            preserve_bytes=data.get("preserve-bytes", False),
            junit=ReportConfig.from_dict(data.get("junit", {})),
            vcr=ReportConfig.from_dict(data.get("vcr", {})),
            har=ReportConfig.from_dict(data.get("har", {})),
            html=HTMLReportConfig.from_dict(data.get("html", {})),
        )

    def update(
        self,
        *,
        formats: list[ReportFormat] | None = None,
        junit_path: str | None = None,
        vcr_path: str | None = None,
        har_path: str | None = None,
        html_path: str | None = None,
        html_title: str | None = None,
        html_include_passed: bool | None = None,
        html_max_body_size: int | None = None,
        directory: Path = DEFAULT_REPORT_DIRECTORY,
        preserve_bytes: bool | None = None,
    ) -> None:
        formats = formats or []
        if junit_path is not None or ReportFormat.JUNIT in formats:
            self.junit.enabled = True
            self.junit.path = Path(junit_path) if junit_path is not None else junit_path
        if vcr_path is not None or ReportFormat.VCR in formats:
            self.vcr.enabled = True
            self.vcr.path = Path(vcr_path) if vcr_path is not None else vcr_path
        if har_path is not None or ReportFormat.HAR in formats:
            self.har.enabled = True
            self.har.path = Path(har_path) if har_path is not None else har_path
        if html_path is not None or ReportFormat.HTML in formats:
            self.html.enabled = True
            self.html.path = Path(html_path) if html_path is not None else self.html.path
        if html_title is not None:
            self.html.title = html_title
        if html_include_passed is not None:
            self.html.include_passed_details = html_include_passed
        if html_max_body_size is not None:
            self.html.max_body_size = html_max_body_size
        if directory != DEFAULT_REPORT_DIRECTORY:
            self.directory = directory
        if preserve_bytes is True:
            self.preserve_bytes = preserve_bytes

    def get_path(self, format: ReportFormat) -> Path:
        """Get the final path for a specific format."""
        report: ReportConfig | HTMLReportConfig = getattr(self, format.value)
        if report.path is not None:
            return report.path

        return self.directory / f"{format.value}-{self._timestamp}.{format.extension}"

"""Enhanced CLI options for HTML reports and ID extraction.

This module provides additional CLI options for the enhanced features.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import click

from autotest.cli.ext.groups import group, grouped_option


def with_enhanced_options(func: Callable) -> Callable:
    """Decorator to add enhanced options to the run command."""

    # HTML Report options
    func = grouped_option(
        "--report-html",
        "report_html_path",
        help="Generate an interactive HTML report at the specified path",
        type=click.Path(dir_okay=False),
        default=None,
        metavar="PATH",
    )(func)

    func = grouped_option(
        "--report-html-title",
        "report_html_title",
        help="Custom title for the HTML report",
        type=str,
        default="API Test Report",
        metavar="TITLE",
    )(func)

    func = grouped_option(
        "--report-include-passed",
        "report_include_passed",
        help="Include full details for passed tests in the HTML report",
        is_flag=True,
        default=False,
    )(func)

    func = grouped_option(
        "--report-max-body-size",
        "report_max_body_size",
        help="Maximum body size to include in reports (bytes)",
        type=click.IntRange(min=1024),
        default=10240,
        metavar="BYTES",
    )(func)

    # ID Extraction options
    func = grouped_option(
        "--extract-ids",
        "extract_ids",
        help="Enable automatic ID extraction and injection",
        is_flag=True,
        default=False,
    )(func)

    func = grouped_option(
        "--no-extract-ids",
        "no_extract_ids",
        help="Disable automatic ID extraction",
        is_flag=True,
        default=False,
    )(func)

    func = grouped_option(
        "--id-injection-strategy",
        "id_injection_strategy",
        help="Strategy for selecting IDs to inject: latest, random, or first",
        type=click.Choice(["latest", "random", "first"]),
        default="latest",
        metavar="STRATEGY",
    )(func)

    func = grouped_option(
        "--id-verbose",
        "id_verbose",
        help="Log all ID extraction and injection decisions",
        is_flag=True,
        default=False,
    )(func)

    return func


def process_enhanced_options(
    params: dict[str, Any],
    handlers: list,
) -> None:
    """Process enhanced options and add appropriate handlers.

    Args:
        params: CLI parameters dictionary.
        handlers: List of handlers to append to.
    """
    # HTML Report
    report_html_path = params.get("report_html_path")
    if report_html_path:
        from autotest.cli.commands.run.handlers.html_report import HTMLReportHandler

        handlers.append(
            HTMLReportHandler(
                output_path=report_html_path,
                title=params.get("report_html_title", "API Test Report"),
                include_passed_details=params.get("report_include_passed", False),
                max_body_size=params.get("report_max_body_size", 10240),
            )
        )

    # ID Extraction
    extract_ids = params.get("extract_ids", False)
    no_extract_ids = params.get("no_extract_ids", False)

    if extract_ids and not no_extract_ids:
        from autotest.cli.commands.run.handlers.id_extraction import IDExtractionHandler

        handlers.append(
            IDExtractionHandler(
                prefer=params.get("id_injection_strategy", "latest"),
                verbose=params.get("id_verbose", False),
            )
        )

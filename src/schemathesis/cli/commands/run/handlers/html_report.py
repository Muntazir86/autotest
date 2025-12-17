"""HTML Report Handler for CLI execution.

This handler collects test data during execution and generates
an HTML report at the end.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from schemathesis.cli.commands.run.handlers.base import EventHandler
from schemathesis.engine.events import (
    EngineFinished,
    EngineStarted,
    PhaseStarted,
    ScenarioFinished,
)
from schemathesis.reporting.collector import DataCollector
from schemathesis.reporting.html_generator import HTMLReportGenerator

if TYPE_CHECKING:
    from schemathesis.cli.commands.run.context import ExecutionContext
    from schemathesis.cli.commands.run.events import LoadingFinished
    from schemathesis.engine.events import EngineEvent


class HTMLReportHandler(EventHandler):
    """Event handler that generates HTML reports."""

    def __init__(
        self,
        output_path: str | Path,
        title: str = "API Test Report",
        include_passed_details: bool = False,
        max_body_size: int = 10240,
        sanitize_headers: list[str] | None = None,
    ) -> None:
        """Initialize the HTML report handler.

        Args:
            output_path: Path where the HTML report will be written.
            title: Title for the report.
            include_passed_details: Include full details for passed tests.
            max_body_size: Maximum body size to capture (bytes).
            sanitize_headers: Additional headers to sanitize.
        """
        self._output_path = Path(output_path)
        self._title = title
        self._include_passed_details = include_passed_details
        self._max_body_size = max_body_size
        self._sanitize_headers = sanitize_headers
        self._collector: DataCollector | None = None
        self._current_phase: str = "unknown"

    def start(self, ctx: ExecutionContext) -> None:
        """Called when execution starts."""
        pass

    def handle_event(self, ctx: ExecutionContext, event: EngineEvent) -> None:
        """Handle an engine event."""
        from schemathesis.cli.commands.run.events import LoadingFinished

        if isinstance(event, LoadingFinished):
            self._handle_loading_finished(event)
        elif isinstance(event, EngineStarted):
            pass  # Collector already initialized
        elif isinstance(event, PhaseStarted):
            self._handle_phase_started(event)
        elif isinstance(event, ScenarioFinished):
            self._handle_scenario_finished(event)
        elif isinstance(event, EngineFinished):
            self._handle_engine_finished(ctx, event)

    def _handle_loading_finished(self, event: LoadingFinished) -> None:
        """Initialize the collector with API info."""
        # Extract API info from schema
        api_name = ""
        api_version = ""

        if event.schema:
            info = event.schema.get("info", {})
            api_name = info.get("title", "")
            api_version = info.get("version", "")

        self._collector = DataCollector(
            api_name=api_name,
            api_version=api_version,
            base_url=event.base_url or "",
            max_body_size=self._max_body_size,
            sanitize_headers=self._sanitize_headers,
            include_passed_details=self._include_passed_details,
        )

    def _handle_phase_started(self, event: PhaseStarted) -> None:
        """Track the current phase."""
        self._current_phase = event.phase.name.value

        if self._collector:
            self._collector.set_phase(self._current_phase)

    def _handle_scenario_finished(self, event: ScenarioFinished) -> None:
        """Collect data from a finished scenario."""
        if self._collector is None:
            return

        # Record results from the scenario recorder
        self._collector.record_from_recorder(
            recorder=event.recorder,
            phase=self._current_phase,
        )

    def _handle_engine_finished(self, ctx: ExecutionContext, event: EngineFinished) -> None:
        """Generate the HTML report."""
        if self._collector is None:
            return

        # Finish the run
        run_info = self._collector.finish()

        # Generate the report
        generator = HTMLReportGenerator(
            title=self._title,
            include_passed_details=self._include_passed_details,
        )

        try:
            report_path = generator.generate(run_info, self._output_path)
            # Print report location
            ctx.console.print(f"\n📊 HTML Report generated: {report_path}")
        except Exception as e:
            ctx.console.print(f"\n⚠️  Failed to generate HTML report: {e}")

    def shutdown(self, ctx: ExecutionContext) -> None:
        """Called when execution ends."""
        pass

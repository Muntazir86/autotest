"""ID Extraction Handler for CLI execution.

This handler manages ID extraction and injection during test execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from autotest.cli.commands.run.handlers.base import EventHandler
from autotest.engine.events import (
    EngineFinished,
    EngineStarted,
    ScenarioFinished,
)
from autotest.extraction.id_extractor import IDExtractor
from autotest.extraction.id_store import IDStore, set_id_store
from autotest.extraction.id_injector import IDInjector
from autotest.extraction.resource_inferrer import ResourceInferrer

if TYPE_CHECKING:
    from autotest.cli.commands.run.context import ExecutionContext
    from autotest.cli.commands.run.events import LoadingFinished
    from autotest.engine.events import EngineEvent


class IDExtractionHandler(EventHandler):
    """Event handler that manages ID extraction and injection."""

    def __init__(
        self,
        prefer: str = "latest",
        fallback_to_generated: bool = True,
        inject_into_body: bool = True,
        inject_into_query: bool = True,
        custom_patterns: list[str] | None = None,
        ignore_fields: set[str] | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize the ID extraction handler.

        Args:
            prefer: ID selection strategy ("latest", "random", "first").
            fallback_to_generated: Use generated values when no stored ID found.
            inject_into_body: Inject IDs into request bodies.
            inject_into_query: Inject IDs into query parameters.
            custom_patterns: Additional regex patterns for ID field names.
            ignore_fields: Fields to ignore when extracting IDs.
            verbose: Log extraction/injection decisions.
        """
        self._prefer = prefer
        self._fallback = fallback_to_generated
        self._inject_body = inject_into_body
        self._inject_query = inject_into_query
        self._custom_patterns = custom_patterns
        self._ignore_fields = ignore_fields
        self._verbose = verbose

        self._store: IDStore | None = None
        self._extractor: IDExtractor | None = None
        self._injector: IDInjector | None = None
        self._inferrer: ResourceInferrer | None = None

    def start(self, ctx: ExecutionContext) -> None:
        """Called when execution starts."""
        pass

    def handle_event(self, ctx: ExecutionContext, event: EngineEvent) -> None:
        """Handle an engine event."""
        from autotest.cli.commands.run.events import LoadingFinished

        if isinstance(event, LoadingFinished):
            self._handle_loading_finished(ctx, event)
        elif isinstance(event, EngineStarted):
            self._enable_hooks()
        elif isinstance(event, ScenarioFinished):
            self._handle_scenario_finished(event)
        elif isinstance(event, EngineFinished):
            self._handle_engine_finished(ctx, event)

    def _handle_loading_finished(self, ctx: ExecutionContext, event: LoadingFinished) -> None:
        """Initialize extraction components with schema info."""
        # Create the ID store
        self._store = IDStore()
        set_id_store(self._store)

        # Create the resource inferrer
        self._inferrer = ResourceInferrer()

        # Extract path parameters from schema for better matching
        path_parameters: set[str] = set()
        if event.schema:
            paths = event.schema.get("paths", {})
            for path, methods in paths.items():
                # Extract parameters from path
                import re
                for match in re.finditer(r"\{([^}]+)\}", path):
                    path_parameters.add(match.group(1))

                # Extract from operation parameters
                if isinstance(methods, dict):
                    for method, operation in methods.items():
                        if isinstance(operation, dict):
                            for param in operation.get("parameters", []):
                                if isinstance(param, dict) and param.get("in") == "path":
                                    path_parameters.add(param.get("name", ""))

        # Create the extractor
        self._extractor = IDExtractor(
            custom_patterns=self._custom_patterns,
            ignore_fields=self._ignore_fields,
            path_parameters=path_parameters,
        )

        # Create the injector
        self._injector = IDInjector(
            id_store=self._store,
            resource_inferrer=self._inferrer,
            prefer=self._prefer,
            fallback_to_generated=self._fallback,
            inject_into_body=self._inject_body,
            inject_into_query=self._inject_query,
            verbose=self._verbose,
        )

    def _enable_hooks(self) -> None:
        """Enable the extraction hooks."""
        from autotest.extraction import hooks as extraction_hooks

        if self._store and self._extractor and self._injector:
            # Set up global state for hooks
            extraction_hooks._extractor = self._extractor
            extraction_hooks._injector = self._injector
            extraction_hooks._inferrer = self._inferrer
            extraction_hooks._enabled = True
            extraction_hooks._verbose = self._verbose

            # Register hooks
            extraction_hooks._register_hooks()

    def _handle_scenario_finished(self, event: ScenarioFinished) -> None:
        """Process completed scenario for ID extraction."""
        if self._store is None or self._extractor is None:
            return

        # Extract IDs from successful responses in the scenario
        for case_id, case_node in event.recorder.cases.items():
            case = case_node.value
            interaction = event.recorder.interactions.get(case_id)

            if interaction is None or interaction.response is None:
                continue

            response = interaction.response

            # Only extract from successful responses
            if response.status_code < 200 or response.status_code >= 300:
                continue

            # Handle DELETE - mark as deleted
            if case.method.upper() == "DELETE":
                for param_name, value in (case.path_parameters or {}).items():
                    if self._is_id_like_param(param_name):
                        resource_type = None
                        if self._inferrer:
                            resource_type = self._inferrer.infer_from_endpoint(
                                case.method, case.path
                            ).resource_type
                        self._store.mark_deleted(value, resource_type)
                continue

            # Extract IDs from response
            try:
                body = response.json()
            except Exception:
                continue

            if body is None:
                continue

            resource_type = None
            if self._inferrer:
                resource_type = self._inferrer.infer_from_endpoint(
                    case.method, case.path
                ).resource_type

            endpoint = f"{case.method.upper()} {case.path}"

            extracted = self._extractor.extract_from_response(
                response_body=body,
                endpoint=endpoint,
                resource_type=resource_type,
                response_headers=dict(response.headers) if response.headers else None,
            )

            if extracted:
                self._store.store_all(extracted)

    def _handle_engine_finished(self, ctx: ExecutionContext, event: EngineFinished) -> None:
        """Print extraction summary."""
        if self._store is None:
            return

        summary = self._store.get_summary()

        if self._verbose or summary["total_ids"] > 0:
            ctx.console.print(f"\n🔑 ID Extraction Summary:")
            ctx.console.print(f"   Total IDs extracted: {summary['total_ids']}")
            ctx.console.print(f"   Active IDs: {summary['active_ids']}")
            ctx.console.print(f"   Deleted IDs: {summary['deleted_ids']}")

            if summary["by_resource_type"]:
                ctx.console.print(f"   By resource type: {summary['by_resource_type']}")

        if self._injector:
            injection_summary = self._injector.get_injection_summary()
            if injection_summary["total_injections"] > 0:
                ctx.console.print(f"   Total injections: {injection_summary['total_injections']}")

        # Disable hooks
        from autotest.extraction import hooks as extraction_hooks
        extraction_hooks.disable_id_extraction()

    def _is_id_like_param(self, name: str) -> bool:
        """Check if a parameter name looks like an ID."""
        import re
        patterns = [r"^id$", r".*_id$", r".*Id$", r"^uuid$", r".*_uuid$"]
        for pattern in patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return True
        return False

    def shutdown(self, ctx: ExecutionContext) -> None:
        """Called when execution ends."""
        set_id_store(None)

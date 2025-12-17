"""Hook integration for ID extraction and injection.

This module provides hooks that integrate the ID extraction system
with Autotest test execution.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from autotest.extraction.id_extractor import IDExtractor
from autotest.extraction.id_store import IDStore, get_id_store, set_id_store
from autotest.extraction.id_injector import IDInjector
from autotest.extraction.resource_inferrer import ResourceInferrer

if TYPE_CHECKING:
    from autotest.core.transport import Response
    from autotest.generation.case import Case
    from autotest.hooks import HookContext


# Global instances (initialized when extraction is enabled)
_extractor: IDExtractor | None = None
_injector: IDInjector | None = None
_inferrer: ResourceInferrer | None = None
_enabled: bool = False
_verbose: bool = False


def enable_id_extraction(
    prefer: str = "latest",
    fallback_to_generated: bool = True,
    inject_into_body: bool = True,
    inject_into_query: bool = True,
    custom_patterns: list[str] | None = None,
    ignore_fields: set[str] | None = None,
    verbose: bool = False,
) -> None:
    """Enable ID extraction and injection.

    Args:
        prefer: ID selection strategy ("latest", "random", "first").
        fallback_to_generated: Use generated values when no stored ID found.
        inject_into_body: Inject IDs into request bodies.
        inject_into_query: Inject IDs into query parameters.
        custom_patterns: Additional regex patterns for ID field names.
        ignore_fields: Fields to ignore when extracting IDs.
        verbose: Log extraction/injection decisions.
    """
    global _extractor, _injector, _inferrer, _enabled, _verbose

    _verbose = verbose
    _inferrer = ResourceInferrer()

    # Create ID store
    store = IDStore()
    set_id_store(store)

    # Create extractor
    _extractor = IDExtractor(
        custom_patterns=custom_patterns,
        ignore_fields=ignore_fields,
    )

    # Create injector
    _injector = IDInjector(
        id_store=store,
        resource_inferrer=_inferrer,
        prefer=prefer,
        fallback_to_generated=fallback_to_generated,
        inject_into_body=inject_into_body,
        inject_into_query=inject_into_query,
        verbose=verbose,
    )

    _enabled = True

    # Register hooks
    _register_hooks()


def disable_id_extraction() -> None:
    """Disable ID extraction and injection."""
    global _extractor, _injector, _inferrer, _enabled

    _enabled = False
    _extractor = None
    _injector = None
    _inferrer = None
    set_id_store(None)

    # Unregister hooks
    _unregister_hooks()


def is_enabled() -> bool:
    """Check if ID extraction is enabled."""
    return _enabled


def get_extractor() -> IDExtractor | None:
    """Get the current ID extractor."""
    return _extractor


def get_injector() -> IDInjector | None:
    """Get the current ID injector."""
    return _injector


def _register_hooks() -> None:
    """Register the extraction hooks with Autotest."""
    from autotest.hooks import GLOBAL_HOOK_DISPATCHER

    # Register after_call hook for extraction
    GLOBAL_HOOK_DISPATCHER.register_hook_with_name(_after_call_hook, "after_call")

    # Register before_call hook for injection
    GLOBAL_HOOK_DISPATCHER.register_hook_with_name(_before_call_hook, "before_call")


def _unregister_hooks() -> None:
    """Unregister the extraction hooks."""
    from autotest.hooks import GLOBAL_HOOK_DISPATCHER

    GLOBAL_HOOK_DISPATCHER.unregister(_after_call_hook)
    GLOBAL_HOOK_DISPATCHER.unregister(_before_call_hook)


def _before_call_hook(context: HookContext, case: Case, **kwargs: Any) -> None:
    """Hook called before each API call to inject IDs."""
    if not _enabled or _injector is None:
        return

    try:
        _injector.inject_into_case(case)
    except Exception as e:
        if _verbose:
            print(f"[ID Injection] Error injecting IDs: {e}")


def _after_call_hook(context: HookContext, case: Case, response: Response) -> None:
    """Hook called after each API call to extract IDs."""
    if not _enabled or _extractor is None:
        return

    # Only extract from successful responses (2xx)
    if response.status_code < 200 or response.status_code >= 300:
        return

    # Handle DELETE requests - mark IDs as deleted
    if case.method.upper() == "DELETE":
        _handle_delete(case, response)
        return

    try:
        # Get response body
        try:
            body = response.json()
        except Exception:
            body = None

        if body is None:
            return

        # Infer resource type
        resource_type = None
        if _inferrer:
            resource_type = _inferrer.infer_from_endpoint(case.method, case.path).resource_type

        # Build endpoint string
        endpoint = f"{case.method.upper()} {case.path}"

        # Extract IDs
        extracted = _extractor.extract_from_response(
            response_body=body,
            endpoint=endpoint,
            resource_type=resource_type,
            response_headers=dict(response.headers) if response.headers else None,
        )

        # Store extracted IDs
        store = get_id_store()
        if store and extracted:
            store.store_all(extracted)

            if _verbose:
                for ext_id in extracted:
                    print(
                        f"[ID Extraction] Extracted {ext_id.field_name}={ext_id.value} "
                        f"from {endpoint} (type: {resource_type})"
                    )

    except Exception as e:
        if _verbose:
            print(f"[ID Extraction] Error extracting IDs: {e}")


def _handle_delete(case: Case, response: Response) -> None:
    """Handle DELETE requests by marking IDs as deleted."""
    store = get_id_store()
    if not store:
        return

    # Try to find the ID that was deleted from path parameters
    for param_name, value in (case.path_parameters or {}).items():
        if _is_id_like_param(param_name):
            # Infer resource type
            resource_type = None
            if _inferrer:
                resource_type = _inferrer.infer_from_endpoint(case.method, case.path).resource_type

            store.mark_deleted(value, resource_type)

            if _verbose:
                print(f"[ID Extraction] Marked {param_name}={value} as deleted")


def _is_id_like_param(name: str) -> bool:
    """Check if a parameter name looks like an ID."""
    import re

    patterns = [r"^id$", r".*_id$", r".*Id$", r"^uuid$", r".*_uuid$"]
    for pattern in patterns:
        if re.match(pattern, name, re.IGNORECASE):
            return True
    return False


def get_extraction_summary() -> dict[str, Any]:
    """Get a summary of ID extraction activity."""
    store = get_id_store()
    injector = get_injector()

    summary: dict[str, Any] = {
        "enabled": _enabled,
        "store": None,
        "injector": None,
    }

    if store:
        summary["store"] = store.get_summary()

    if injector:
        summary["injector"] = injector.get_injection_summary()

    return summary

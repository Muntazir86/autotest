"""Smart ID Extraction Module for Autotest.

This module provides:
- Automatic ID detection from API responses
- Thread-safe ID storage with context
- ID injection into subsequent requests
- Resource type inference from endpoints
"""

from __future__ import annotations

from autotest.extraction.id_extractor import IDExtractor, ExtractedID
from autotest.extraction.id_store import IDStore, get_id_store, set_id_store
from autotest.extraction.id_injector import IDInjector
from autotest.extraction.resource_inferrer import ResourceInferrer
from autotest.extraction.hooks import (
    enable_id_extraction,
    disable_id_extraction,
    is_enabled,
    get_extraction_summary,
)

__all__ = [
    "IDExtractor",
    "ExtractedID",
    "IDStore",
    "get_id_store",
    "set_id_store",
    "IDInjector",
    "ResourceInferrer",
    "enable_id_extraction",
    "disable_id_extraction",
    "is_enabled",
    "get_extraction_summary",
]

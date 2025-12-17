from __future__ import annotations

from autotest import errors, graphql, openapi, pytest
from autotest import extraction, reporting
from autotest.auths import AuthContext, AuthProvider, auth
from autotest.checks import CheckContext, CheckFunction, check
from autotest.config import AutotestConfig as Config
from autotest.core.deserialization import DeserializationContext, deserializer
from autotest.core.transport import Response
from autotest.core.version import AUTOTEST_VERSION
from autotest.generation import GenerationMode, stateful
from autotest.generation.case import Case
from autotest.generation.metrics import MetricContext, MetricFunction, metric
from autotest.hooks import HookContext, hook
from autotest.schemas import APIOperation, BaseSchema
from autotest.transport import SerializationContext, serializer

__version__ = AUTOTEST_VERSION

__all__ = [
    "__version__",
    # Core data structures
    "Case",
    "Response",
    "APIOperation",
    "BaseSchema",
    "Config",
    "GenerationMode",
    "stateful",
    # Public errors
    "errors",
    # Spec or usage specific namespaces
    "openapi",
    "graphql",
    "pytest",
    # Hooks
    "hook",
    "HookContext",
    # Checks
    "check",
    "CheckContext",
    "CheckFunction",
    # Auth
    "auth",
    "AuthContext",
    "AuthProvider",
    # Targeted Property-based Testing
    "metric",
    "MetricContext",
    "MetricFunction",
    # Response deserialization
    "deserializer",
    "DeserializationContext",
    # Serialization
    "serializer",
    "SerializationContext",
    # Enhanced features
    "extraction",
    "reporting",
]

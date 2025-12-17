from __future__ import annotations

import enum
import json
import re
from collections.abc import Mapping
from os import PathLike
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from autotest.config import AutotestConfig
from autotest.core import media_types
from autotest.core.deserialization import deserialize_yaml
from autotest.core.errors import LoaderError, LoaderErrorKind
from autotest.core.loaders import load_from_url, prepare_request_kwargs, raise_for_status, require_relative_url
from autotest.hooks import HookContext, dispatch
from autotest.python import asgi, wsgi

if TYPE_CHECKING:
    from autotest.specs.openapi.schemas import OpenApiSchema


def from_asgi(path: str, app: Any, *, config: AutotestConfig | None = None, **kwargs: Any) -> OpenApiSchema:
    """Load OpenAPI schema from an ASGI application.

    Args:
        path: Relative URL path to the OpenAPI schema endpoint (e.g., "/openapi.json")
        app: ASGI application instance
        config: Custom configuration. If `None`, uses auto-discovered config
        **kwargs: Additional request parameters passed to the ASGI test client

    Example:
        ```python
        from fastapi import FastAPI
        import autotest

        app = FastAPI()
        schema = autotest.openapi.from_asgi("/openapi.json", app)
        ```

    """
    require_relative_url(path)
    client = asgi.get_client(app)
    response = load_from_url(client.get, url=path, **kwargs)
    content_type = detect_content_type(headers=response.headers, path=path)
    schema = load_content(response.text, content_type)
    loaded = from_dict(schema=schema, config=config)
    loaded.app = app
    loaded.location = path
    return loaded


def from_wsgi(path: str, app: Any, *, config: AutotestConfig | None = None, **kwargs: Any) -> OpenApiSchema:
    """Load OpenAPI schema from a WSGI application.

    Args:
        path: Relative URL path to the OpenAPI schema endpoint (e.g., "/openapi.json")
        app: WSGI application instance
        config: Custom configuration. If `None`, uses auto-discovered config
        **kwargs: Additional request parameters passed to the WSGI test client

    Example:
        ```python
        from flask import Flask
        import autotest

        app = Flask(__name__)
        schema = autotest.openapi.from_wsgi("/openapi.json", app)
        ```

    """
    require_relative_url(path)
    prepare_request_kwargs(kwargs)
    client = wsgi.get_client(app)
    response = client.get(path=path, **kwargs)
    raise_for_status(response)
    content_type = detect_content_type(headers=response.headers, path=path)
    schema = load_content(response.text, content_type)
    loaded = from_dict(schema=schema, config=config)
    loaded.app = app
    loaded.location = path
    return loaded


def from_url(
    url: str, *, config: AutotestConfig | None = None, wait_for_schema: float | None = None, **kwargs: Any
) -> OpenApiSchema:
    """Load OpenAPI schema from a URL.

    Args:
        url: Full URL to the OpenAPI schema
        config: Custom configuration. If `None`, uses auto-discovered config
        wait_for_schema: Maximum time in seconds to wait for schema availability
        **kwargs: Additional parameters passed to `requests.get()` (headers, timeout, auth, etc.)

    Example:
        ```python
        import autotest

        # Basic usage
        schema = autotest.openapi.from_url("https://api.example.com/openapi.json")

        # With authentication and timeout
        schema = autotest.openapi.from_url(
            "https://api.example.com/openapi.json",
            headers={"Authorization": "Bearer token"},
            timeout=30,
            wait_for_schema=10.0
        )
        ```

    """
    import requests

    if wait_for_schema is None:
        if config is None:
            config = AutotestConfig.discover()
        wait_for_schema = config.wait_for_schema

    response = load_from_url(requests.get, url=url, wait_for_schema=wait_for_schema, **kwargs)
    content_type = detect_content_type(headers=response.headers, path=url)
    schema = load_content(response.text, content_type)
    loaded = from_dict(schema=schema, config=config)
    loaded.location = url
    return loaded


def from_path(
    path: PathLike | str, *, config: AutotestConfig | None = None, encoding: str = "utf-8"
) -> OpenApiSchema:
    """Load OpenAPI schema from a filesystem path.

    Args:
        path: File path to the OpenAPI schema (supports JSON / YAML)
        config: Custom configuration. If `None`, uses auto-discovered config
        encoding: Text encoding for reading the file

    Example:
        ```python
        import autotest

        # Load from file
        schema = autotest.openapi.from_path("./specs/openapi.yaml")

        # With custom encoding
        schema = autotest.openapi.from_path("./specs/openapi.json", encoding="cp1252")
        ```

    """
    with open(path, encoding=encoding) as file:
        content_type = detect_content_type(headers=None, path=str(path))
        schema = load_content(file.read(), content_type)
    loaded = from_dict(schema=schema, config=config)
    loaded.location = Path(path).absolute().as_uri()
    return loaded


def from_file(file: IO[str] | str, *, config: AutotestConfig | None = None) -> OpenApiSchema:
    """Load OpenAPI schema from a file-like object or string.

    Args:
        file: File-like object or raw string containing the OpenAPI schema
        config: Custom configuration. If `None`, uses auto-discovered config

    Example:
        ```python
        import autotest

        # From string
        schema_content = '{"openapi": "3.0.0", "info": {"title": "API"}}'
        schema = autotest.openapi.from_file(schema_content)

        # From file object
        with open("openapi.yaml") as f:
            schema = autotest.openapi.from_file(f)
        ```

    """
    if isinstance(file, str):
        data = file
    else:
        data = file.read()
    try:
        schema = json.loads(data)
    except json.JSONDecodeError:
        schema = _load_yaml(data)
    return from_dict(schema, config=config)


def from_dict(schema: dict[str, Any], *, config: AutotestConfig | None = None) -> OpenApiSchema:
    """Load OpenAPI schema from a dictionary.

    Args:
        schema: Dictionary containing the parsed OpenAPI schema
        config: Custom configuration. If `None`, uses auto-discovered config

    Example:
        ```python
        import autotest

        schema_dict = {
            "openapi": "3.0.0",
            "info": {"title": "My API", "version": "1.0.0"},
            "paths": {"/users": {"get": {"responses": {"200": {"description": "OK"}}}}}
        }

        schema = autotest.openapi.from_dict(schema_dict)
        ```

    """
    if not isinstance(schema, dict):
        raise LoaderError(LoaderErrorKind.OPEN_API_INVALID_SCHEMA, SCHEMA_INVALID_ERROR)
    hook_context = HookContext()
    dispatch("before_load_schema", hook_context, schema)

    if config is None:
        config = AutotestConfig.discover()
    project_config = config.projects.get(schema)

    version = schema.get("openapi")
    if version is not None and not OPENAPI_VERSION_RE.match(version):
        raise LoaderError(
            LoaderErrorKind.OPEN_API_UNSUPPORTED_VERSION,
            f"The provided schema uses Open API {version}, which is currently not supported.",
        )
    if version is None and "swagger" not in schema:
        raise LoaderError(
            LoaderErrorKind.OPEN_API_UNSPECIFIED_VERSION,
            "Unable to determine the Open API version as it's not specified in the document.",
        )
    from autotest.specs.openapi.schemas import OpenApiSchema

    instance = OpenApiSchema(raw_schema=schema, config=project_config)
    instance.filter_set = project_config.operations.filter_set_with(include=instance.filter_set)
    dispatch("after_load_schema", hook_context, instance)
    return instance


class ContentType(enum.Enum):
    """Known content types for schema files."""

    JSON = enum.auto()
    YAML = enum.auto()
    UNKNOWN = enum.auto()


def detect_content_type(*, headers: Mapping[str, str] | None = None, path: str | None = None) -> ContentType:
    """Detect content type from various sources."""
    if headers is not None and (content_type := _detect_from_headers(headers)) != ContentType.UNKNOWN:
        return content_type
    if path is not None and (content_type := _detect_from_path(path)) != ContentType.UNKNOWN:
        return content_type
    return ContentType.UNKNOWN


def _detect_from_headers(headers: Mapping[str, str]) -> ContentType:
    """Detect content type from HTTP headers."""
    content_type = headers.get("Content-Type", "").lower()
    try:
        if content_type and media_types.is_json(content_type):
            return ContentType.JSON
        if content_type and media_types.is_yaml(content_type):
            return ContentType.YAML
    except ValueError:
        pass
    return ContentType.UNKNOWN


def _detect_from_path(path: str) -> ContentType:
    """Detect content type from file path."""
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return ContentType.JSON
    if suffix in (".yaml", ".yml"):
        return ContentType.YAML
    return ContentType.UNKNOWN


def load_content(content: str, content_type: ContentType) -> dict[str, Any]:
    """Load content using appropriate parser."""
    if content_type == ContentType.JSON:
        return _load_json(content)
    if content_type == ContentType.YAML:
        return _load_yaml(content)
    # If type is unknown, try JSON first, then YAML
    try:
        return _load_json(content)
    except LoaderError:
        return _load_yaml(content)


def _load_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise LoaderError(
            LoaderErrorKind.SYNTAX_ERROR,
            SCHEMA_SYNTAX_ERROR,
            extras=[entry for entry in str(exc).splitlines() if entry],
        ) from exc


def _load_yaml(content: str) -> dict[str, Any]:
    import yaml

    try:
        return deserialize_yaml(content)
    except yaml.YAMLError as exc:
        raise LoaderError(
            LoaderErrorKind.SYNTAX_ERROR,
            SCHEMA_SYNTAX_ERROR,
            extras=[entry for entry in str(exc).splitlines() if entry],
        ) from exc


SCHEMA_INVALID_ERROR = "The provided API schema does not appear to be a valid OpenAPI schema"
SCHEMA_SYNTAX_ERROR = "API schema does not appear syntactically valid"
OPENAPI_VERSION_RE = re.compile(r"^3\.[01]\.[0-9](-.+)?$")

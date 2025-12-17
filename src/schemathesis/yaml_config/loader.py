"""Configuration loader for YAML configuration.

Handles loading, inheritance resolution, and variable substitution for YAML config files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from schemathesis.yaml_config.errors import (
    CircularInheritanceError,
    ConfigLoadError,
    ConfigValidationError,
    YAMLConfigError,
)
from schemathesis.yaml_config.merger import ConfigMerger
from schemathesis.yaml_config.resolver import VariableResolver
from schemathesis.yaml_config.schema import YAMLConfig
from schemathesis.yaml_config.validator import ConfigValidator


class ConfigLoader:
    """Loads and processes YAML configuration files."""

    # Default config file names to search for
    DEFAULT_CONFIG_NAMES = [
        "api-tester.yaml",
        "api-tester.yml",
        "schemathesis.yaml",
        "schemathesis.yml",
        ".api-tester.yaml",
        ".api-tester.yml",
    ]

    def __init__(self) -> None:
        """Initialize the config loader."""
        self.merger = ConfigMerger()
        self._loaded_paths: set[str] = set()

    def load(
        self,
        path: str | Path,
        env: str | None = None,
        resolve_variables: bool = True,
        validate: bool = True,
    ) -> YAMLConfig:
        """Load a configuration file.

        Args:
            path: Path to the configuration file.
            env: Environment to apply (overrides config's environment setting).
            resolve_variables: Whether to resolve ${...} variables.
            validate: Whether to validate the configuration.

        Returns:
            Loaded and processed YAMLConfig object.

        Raises:
            ConfigLoadError: If the file cannot be loaded.
            ConfigValidationError: If validation fails.
            CircularInheritanceError: If circular inheritance is detected.
        """
        self._loaded_paths = set()
        path = Path(path).resolve()

        if not path.exists():
            raise ConfigLoadError(f"Configuration file not found: {path}", str(path))

        # Load the config with inheritance
        config_dict = self._load_with_inheritance(path)

        # Resolve variables if requested
        if resolve_variables:
            resolver = VariableResolver(base_path=path.parent, config_context=config_dict)
            config_dict = resolver.resolve(config_dict)

        # Validate if requested
        if validate:
            validator = ConfigValidator(base_path=path.parent)
            errors = validator.validate(config_dict, str(path))
            if errors:
                # Raise the first error
                raise errors[0]

        # Parse into Pydantic model
        try:
            config = YAMLConfig.model_validate(config_dict)
        except Exception as e:
            raise ConfigValidationError(str(e), str(path))

        # Apply environment overrides
        target_env = env or config.environment
        if target_env and target_env in config.environments:
            config = config.get_effective_config(target_env)

        return config

    def load_from_string(
        self,
        content: str,
        base_path: Path | None = None,
        env: str | None = None,
        resolve_variables: bool = True,
    ) -> YAMLConfig:
        """Load configuration from a YAML string.

        Args:
            content: YAML content string.
            base_path: Base path for resolving relative paths.
            env: Environment to apply.
            resolve_variables: Whether to resolve ${...} variables.

        Returns:
            Loaded YAMLConfig object.
        """
        try:
            config_dict = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"Invalid YAML: {e}")

        base_path = base_path or Path.cwd()

        # Resolve variables if requested
        if resolve_variables:
            resolver = VariableResolver(base_path=base_path, config_context=config_dict)
            config_dict = resolver.resolve(config_dict)

        # Parse into Pydantic model
        try:
            config = YAMLConfig.model_validate(config_dict)
        except Exception as e:
            raise ConfigValidationError(str(e))

        # Apply environment overrides
        target_env = env or config.environment
        if target_env and target_env in config.environments:
            config = config.get_effective_config(target_env)

        return config

    def discover(self, start_dir: Path | None = None) -> YAMLConfig | None:
        """Discover and load a configuration file.

        Searches for configuration files in the following order:
        1. Current directory
        2. Parent directories up to git root or filesystem root

        Args:
            start_dir: Directory to start searching from.

        Returns:
            Loaded YAMLConfig if found, None otherwise.
        """
        current_dir = start_dir or Path.cwd()

        while True:
            # Check for config files in current directory
            for name in self.DEFAULT_CONFIG_NAMES:
                config_path = current_dir / name
                if config_path.exists():
                    return self.load(config_path)

            # Check for pyproject.toml with [tool.api-tester] section
            pyproject_path = current_dir / "pyproject.toml"
            if pyproject_path.exists():
                config = self._load_from_pyproject(pyproject_path)
                if config is not None:
                    return config

            # Stop at git root
            if (current_dir / ".git").exists():
                break

            # Stop at filesystem root
            parent = current_dir.parent
            if parent == current_dir:
                break
            current_dir = parent

        return None

    def _load_with_inheritance(self, path: Path) -> dict[str, Any]:
        """Load a config file and resolve inheritance.

        Args:
            path: Path to the configuration file.

        Returns:
            Merged configuration dictionary.
        """
        path_str = str(path.resolve())

        # Check for circular inheritance
        if path_str in self._loaded_paths:
            chain = list(self._loaded_paths) + [path_str]
            raise CircularInheritanceError(chain)

        self._loaded_paths.add(path_str)

        try:
            content = path.read_text(encoding="utf-8")
            config_dict = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise ConfigLoadError(f"Invalid YAML: {e}", path_str)
        except Exception as e:
            raise ConfigLoadError(str(e), path_str)

        # Process extends
        extends = config_dict.pop("extends", [])
        if isinstance(extends, str):
            extends = [extends]

        if extends:
            # Load parent configs
            parent_configs = []
            for extend_path in extends:
                resolved_path = self._resolve_extend_path(extend_path, path.parent)
                parent_config = self._load_with_inheritance(resolved_path)
                parent_configs.append(parent_config)

            # Merge all parent configs
            if parent_configs:
                merged_parent = self.merger.merge_multiple(parent_configs)
                # Merge current config on top of parents
                config_dict = self.merger.merge(merged_parent, config_dict)

        return config_dict

    def _resolve_extend_path(self, extend_path: str, base_dir: Path) -> Path:
        """Resolve an extends path relative to the config file.

        Args:
            extend_path: The path from the extends directive.
            base_dir: Directory of the current config file.

        Returns:
            Resolved absolute path.
        """
        path = Path(extend_path)
        if path.is_absolute():
            return path
        return (base_dir / path).resolve()

    def _load_from_pyproject(self, path: Path) -> YAMLConfig | None:
        """Load configuration from pyproject.toml [tool.api-tester] section.

        Args:
            path: Path to pyproject.toml.

        Returns:
            YAMLConfig if section exists, None otherwise.
        """
        try:
            import sys

            if sys.version_info < (3, 11):
                import tomli as tomllib
            else:
                import tomllib

            content = path.read_text(encoding="utf-8")
            data = tomllib.loads(content)

            tool_config = data.get("tool", {}).get("api-tester")
            if tool_config:
                return YAMLConfig.model_validate(tool_config)

        except Exception:
            pass

        return None

    def validate_file(self, path: str | Path) -> list[ConfigValidationError | str]:
        """Validate a configuration file without fully loading it.

        Args:
            path: Path to the configuration file.

        Returns:
            List of validation errors and warnings.
        """
        path = Path(path).resolve()
        issues: list[ConfigValidationError | str] = []

        if not path.exists():
            issues.append(ConfigValidationError(f"File not found: {path}", str(path)))
            return issues

        try:
            content = path.read_text(encoding="utf-8")
            config_dict = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            issues.append(ConfigValidationError(f"Invalid YAML: {e}", str(path)))
            return issues

        validator = ConfigValidator(base_path=path.parent)
        errors = validator.validate(config_dict, str(path))
        issues.extend(errors)
        issues.extend(validator.get_warnings())

        return issues

    def show_resolved(self, path: str | Path, env: str | None = None) -> dict[str, Any]:
        """Load and show the fully resolved configuration.

        Args:
            path: Path to the configuration file.
            env: Environment to apply.

        Returns:
            Fully resolved configuration as a dictionary.
        """
        config = self.load(path, env=env)
        return config.model_dump()


def load_config(
    path: str | Path | None = None,
    env: str | None = None,
    auto_discover: bool = True,
) -> YAMLConfig | None:
    """Convenience function to load configuration.

    Args:
        path: Path to configuration file. If None, auto-discovers.
        env: Environment to apply.
        auto_discover: Whether to auto-discover config if path is None.

    Returns:
        Loaded YAMLConfig or None if not found.
    """
    loader = ConfigLoader()

    if path:
        return loader.load(path, env=env)
    elif auto_discover:
        return loader.discover()

    return None

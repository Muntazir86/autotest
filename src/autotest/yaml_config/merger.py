"""Configuration merger for YAML configuration.

Handles deep merging of configuration dictionaries with support for
special merge strategies for arrays.
"""

from __future__ import annotations

from typing import Any


class ConfigMerger:
    """Merges configuration dictionaries with support for special merge strategies."""

    # Special keys for array merge strategies
    APPEND_KEY = "$append"
    PREPEND_KEY = "$prepend"
    MERGE_KEY = "$merge"
    REPLACE_KEY = "$replace"

    def merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Args:
            base: The base configuration dictionary.
            override: The override configuration dictionary.

        Returns:
            A new dictionary with merged values.

        Merge rules:
        - Scalar values: override replaces base
        - Dicts: recursively merged
        - Lists: replaced by default, unless special merge keys are used
        """
        result = base.copy()

        for key, value in override.items():
            if key not in result:
                result[key] = self._deep_copy(value)
            elif isinstance(result[key], dict) and isinstance(value, dict):
                # Check for special array merge strategies in the override dict
                if self._has_merge_strategy(value):
                    result[key] = self._apply_merge_strategy(result[key], value)
                else:
                    result[key] = self.merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, dict):
                # Override is a dict with potential merge strategy for a list
                if self._has_merge_strategy(value):
                    result[key] = self._apply_merge_strategy(result[key], value)
                else:
                    result[key] = self._deep_copy(value)
            else:
                result[key] = self._deep_copy(value)

        return result

    def _has_merge_strategy(self, value: dict[str, Any]) -> bool:
        """Check if a dict contains a merge strategy key."""
        return any(
            key in value
            for key in (self.APPEND_KEY, self.PREPEND_KEY, self.MERGE_KEY, self.REPLACE_KEY)
        )

    def _apply_merge_strategy(self, base: Any, strategy_dict: dict[str, Any]) -> Any:
        """Apply a merge strategy to a base value."""
        if self.REPLACE_KEY in strategy_dict:
            return self._deep_copy(strategy_dict[self.REPLACE_KEY])

        if not isinstance(base, list):
            # If base is not a list, just use the strategy value directly
            for key in (self.APPEND_KEY, self.PREPEND_KEY, self.MERGE_KEY):
                if key in strategy_dict:
                    return self._deep_copy(strategy_dict[key])
            return base

        result = list(base)

        if self.APPEND_KEY in strategy_dict:
            items = strategy_dict[self.APPEND_KEY]
            if isinstance(items, list):
                result.extend(items)
            else:
                result.append(items)

        if self.PREPEND_KEY in strategy_dict:
            items = strategy_dict[self.PREPEND_KEY]
            if isinstance(items, list):
                result = items + result
            else:
                result = [items] + result

        if self.MERGE_KEY in strategy_dict:
            items = strategy_dict[self.MERGE_KEY]
            if isinstance(items, list):
                # Add unique items only
                for item in items:
                    if item not in result:
                        result.append(item)
            elif items not in result:
                result.append(items)

        return result

    def _deep_copy(self, value: Any) -> Any:
        """Create a deep copy of a value."""
        if isinstance(value, dict):
            return {k: self._deep_copy(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._deep_copy(item) for item in value]
        return value

    def merge_multiple(self, configs: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge multiple configuration dictionaries in order.

        Args:
            configs: List of configuration dictionaries to merge.

        Returns:
            A single merged configuration dictionary.
        """
        if not configs:
            return {}

        result = self._deep_copy(configs[0])
        for config in configs[1:]:
            result = self.merge(result, config)

        return result

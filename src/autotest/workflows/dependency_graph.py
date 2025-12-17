"""Dependency graph for workflow step ordering.

Handles dependency resolution, cycle detection, and topological sorting.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from autotest.workflows.errors import CircularDependencyError, DependencyNotFoundError
from autotest.workflows.models import WorkflowStep


class DependencyGraph:
    """Manages step dependencies and execution order."""

    def __init__(self, workflow_name: str | None = None) -> None:
        """Initialize the dependency graph.

        Args:
            workflow_name: Name of the workflow for error reporting.
        """
        self.workflow_name = workflow_name
        self._nodes: dict[str, WorkflowStep] = {}
        self._edges: dict[str, set[str]] = defaultdict(set)  # step -> dependencies
        self._reverse_edges: dict[str, set[str]] = defaultdict(set)  # step -> dependents

    def add_step(self, step: WorkflowStep) -> None:
        """Add a step to the graph.

        Args:
            step: The workflow step to add.
        """
        self._nodes[step.name] = step
        for dep in step.depends_on:
            self._edges[step.name].add(dep)
            self._reverse_edges[dep].add(step.name)

    def add_steps(self, steps: list[WorkflowStep]) -> None:
        """Add multiple steps to the graph.

        Args:
            steps: List of workflow steps to add.
        """
        for step in steps:
            self.add_step(step)

    def validate(self) -> None:
        """Validate the dependency graph.

        Raises:
            DependencyNotFoundError: If a dependency references a non-existent step.
            CircularDependencyError: If circular dependencies are detected.
        """
        # Check for missing dependencies
        for step_name, dependencies in self._edges.items():
            for dep in dependencies:
                if dep not in self._nodes:
                    raise DependencyNotFoundError(step_name, dep, self.workflow_name)

        # Check for cycles
        cycle = self._detect_cycle()
        if cycle:
            raise CircularDependencyError(cycle, self.workflow_name)

    def _detect_cycle(self) -> list[str] | None:
        """Detect cycles in the dependency graph using DFS.

        Returns:
            List of step names forming a cycle, or None if no cycle exists.
        """
        WHITE = 0  # Not visited
        GRAY = 1  # Currently visiting (in stack)
        BLACK = 2  # Finished visiting

        color: dict[str, int] = {node: WHITE for node in self._nodes}
        parent: dict[str, str | None] = {node: None for node in self._nodes}

        def dfs(node: str, path: list[str]) -> list[str] | None:
            color[node] = GRAY
            path.append(node)

            for dep in self._edges.get(node, set()):
                if dep not in self._nodes:
                    continue

                if color[dep] == GRAY:
                    # Found a cycle
                    cycle_start = path.index(dep)
                    return path[cycle_start:] + [dep]
                elif color[dep] == WHITE:
                    result = dfs(dep, path)
                    if result:
                        return result

            path.pop()
            color[node] = BLACK
            return None

        for node in self._nodes:
            if color[node] == WHITE:
                result = dfs(node, [])
                if result:
                    return result

        return None

    def get_execution_order(self) -> list[str]:
        """Get the topological order for step execution.

        Returns:
            List of step names in execution order.

        Raises:
            CircularDependencyError: If circular dependencies exist.
        """
        self.validate()
        return self._topological_sort()

    def _topological_sort(self) -> list[str]:
        """Perform topological sort using Kahn's algorithm.

        Returns:
            List of step names in topological order.
        """
        # Calculate in-degree for each node
        in_degree: dict[str, int] = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._edges.get(node, set()):
                if dep in self._nodes:
                    in_degree[node] += 1

        # Start with nodes that have no dependencies
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result: list[str] = []

        while queue:
            # Sort queue for deterministic ordering
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            # Reduce in-degree for dependent nodes
            for dependent in self._reverse_edges.get(node, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    def get_parallel_groups(self) -> list[list[str]]:
        """Get groups of steps that can be executed in parallel.

        Returns:
            List of groups, where each group contains steps that can run in parallel.
        """
        self.validate()

        # Calculate in-degree for each node
        in_degree: dict[str, int] = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._edges.get(node, set()):
                if dep in self._nodes:
                    in_degree[node] += 1

        groups: list[list[str]] = []
        remaining = set(self._nodes.keys())

        while remaining:
            # Find all nodes with no remaining dependencies
            ready = [node for node in remaining if in_degree[node] == 0]
            if not ready:
                break

            ready.sort()  # Deterministic ordering
            groups.append(ready)

            # Remove ready nodes and update in-degrees
            for node in ready:
                remaining.remove(node)
                for dependent in self._reverse_edges.get(node, set()):
                    if dependent in in_degree:
                        in_degree[dependent] -= 1

        return groups

    def get_dependencies(self, step_name: str) -> set[str]:
        """Get direct dependencies of a step.

        Args:
            step_name: Name of the step.

        Returns:
            Set of step names that this step depends on.
        """
        return self._edges.get(step_name, set()).copy()

    def get_all_dependencies(self, step_name: str) -> set[str]:
        """Get all transitive dependencies of a step.

        Args:
            step_name: Name of the step.

        Returns:
            Set of all step names that this step depends on (directly or indirectly).
        """
        result: set[str] = set()
        queue = list(self._edges.get(step_name, set()))

        while queue:
            dep = queue.pop(0)
            if dep not in result and dep in self._nodes:
                result.add(dep)
                queue.extend(self._edges.get(dep, set()))

        return result

    def get_dependents(self, step_name: str) -> set[str]:
        """Get steps that depend on a given step.

        Args:
            step_name: Name of the step.

        Returns:
            Set of step names that depend on this step.
        """
        return self._reverse_edges.get(step_name, set()).copy()

    def get_all_dependents(self, step_name: str) -> set[str]:
        """Get all steps that transitively depend on a given step.

        Args:
            step_name: Name of the step.

        Returns:
            Set of all step names that depend on this step (directly or indirectly).
        """
        result: set[str] = set()
        queue = list(self._reverse_edges.get(step_name, set()))

        while queue:
            dep = queue.pop(0)
            if dep not in result and dep in self._nodes:
                result.add(dep)
                queue.extend(self._reverse_edges.get(dep, set()))

        return result

    def get_step(self, step_name: str) -> WorkflowStep | None:
        """Get a step by name.

        Args:
            step_name: Name of the step.

        Returns:
            The WorkflowStep or None if not found.
        """
        return self._nodes.get(step_name)

    def get_all_steps(self) -> list[WorkflowStep]:
        """Get all steps in the graph.

        Returns:
            List of all WorkflowStep objects.
        """
        return list(self._nodes.values())

    def is_ready(self, step_name: str, completed: set[str]) -> bool:
        """Check if a step is ready to execute.

        Args:
            step_name: Name of the step to check.
            completed: Set of already completed step names.

        Returns:
            True if all dependencies are satisfied.
        """
        dependencies = self._edges.get(step_name, set())
        return all(dep in completed for dep in dependencies)

    def get_ready_steps(self, completed: set[str]) -> list[str]:
        """Get all steps that are ready to execute.

        Args:
            completed: Set of already completed step names.

        Returns:
            List of step names that are ready to execute.
        """
        ready = []
        for step_name in self._nodes:
            if step_name not in completed and self.is_ready(step_name, completed):
                ready.append(step_name)
        return sorted(ready)  # Deterministic ordering

    def __len__(self) -> int:
        """Return the number of steps in the graph."""
        return len(self._nodes)

    def __contains__(self, step_name: str) -> bool:
        """Check if a step exists in the graph."""
        return step_name in self._nodes

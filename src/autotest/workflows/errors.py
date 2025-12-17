"""Error classes for workflow system."""

from __future__ import annotations

from typing import Any


class WorkflowError(Exception):
    """Base exception for workflow errors."""

    def __init__(self, message: str, workflow_name: str | None = None) -> None:
        self.message = message
        self.workflow_name = workflow_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.workflow_name:
            return f"[{self.workflow_name}] {self.message}"
        return self.message


class WorkflowParseError(WorkflowError):
    """Raised when workflow parsing fails."""

    def __init__(
        self,
        message: str,
        workflow_name: str | None = None,
        file_path: str | None = None,
        line: int | None = None,
    ) -> None:
        self.file_path = file_path
        self.line = line
        super().__init__(message, workflow_name)

    def _format_message(self) -> str:
        parts = []
        if self.file_path:
            if self.line:
                parts.append(f"{self.file_path}:{self.line}")
            else:
                parts.append(self.file_path)
        if self.workflow_name:
            parts.append(f"workflow '{self.workflow_name}'")
        parts.append(self.message)
        return ": ".join(parts)


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails."""

    def __init__(
        self,
        message: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.step_name = step_name
        super().__init__(message, workflow_name)

    def _format_message(self) -> str:
        parts = []
        if self.workflow_name:
            parts.append(f"workflow '{self.workflow_name}'")
        if self.step_name:
            parts.append(f"step '{self.step_name}'")
        parts.append(self.message)
        return ": ".join(parts)


class WorkflowValidationError(WorkflowError):
    """Raised when workflow validation fails."""

    def __init__(
        self,
        message: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
        field: str | None = None,
    ) -> None:
        self.step_name = step_name
        self.field = field
        super().__init__(message, workflow_name)

    def _format_message(self) -> str:
        parts = []
        if self.workflow_name:
            parts.append(f"workflow '{self.workflow_name}'")
        if self.step_name:
            parts.append(f"step '{self.step_name}'")
        if self.field:
            parts.append(f"field '{self.field}'")
        parts.append(self.message)
        return ": ".join(parts)


class CircularDependencyError(WorkflowError):
    """Raised when circular dependencies are detected in workflow steps."""

    def __init__(self, cycle: list[str], workflow_name: str | None = None) -> None:
        self.cycle = cycle
        message = f"Circular dependency detected: {' -> '.join(cycle)}"
        super().__init__(message, workflow_name)


class StepExecutionError(WorkflowError):
    """Raised when a workflow step fails to execute."""

    def __init__(
        self,
        message: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.step_name = step_name
        self.cause = cause
        super().__init__(message, workflow_name)

    def _format_message(self) -> str:
        parts = []
        if self.workflow_name:
            parts.append(f"workflow '{self.workflow_name}'")
        if self.step_name:
            parts.append(f"step '{self.step_name}'")
        parts.append(self.message)
        if self.cause:
            parts.append(f"caused by: {self.cause}")
        return ": ".join(parts)


class ExpressionError(WorkflowError):
    """Raised when expression evaluation fails."""

    def __init__(
        self,
        expression: str,
        message: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.expression = expression
        self.step_name = step_name
        super().__init__(f"Expression '{expression}': {message}", workflow_name)


class DependencyNotFoundError(WorkflowError):
    """Raised when a step dependency is not found."""

    def __init__(
        self,
        step_name: str,
        dependency_name: str,
        workflow_name: str | None = None,
    ) -> None:
        self.step_name = step_name
        self.dependency_name = dependency_name
        message = f"Step '{step_name}' depends on unknown step '{dependency_name}'"
        super().__init__(message, workflow_name)


class VariableNotFoundError(WorkflowError):
    """Raised when a variable is not found in context."""

    def __init__(
        self,
        variable_name: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.variable_name = variable_name
        self.step_name = step_name
        message = f"Variable '{variable_name}' not found"
        super().__init__(message, workflow_name)


class ExtractionError(WorkflowError):
    """Raised when data extraction from response fails."""

    def __init__(
        self,
        path: str,
        message: str,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.path = path
        self.step_name = step_name
        super().__init__(f"Extraction '{path}': {message}", workflow_name)


class ExpectationError(WorkflowError):
    """Raised when response doesn't match expectations."""

    def __init__(
        self,
        expectation: str,
        actual: Any,
        expected: Any,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.expectation = expectation
        self.actual = actual
        self.expected = expected
        self.step_name = step_name
        message = f"Expectation failed: {expectation} (expected {expected!r}, got {actual!r})"
        super().__init__(message, workflow_name)


class TimeoutError(WorkflowError):
    """Raised when a workflow or step times out."""

    def __init__(
        self,
        timeout_seconds: float,
        workflow_name: str | None = None,
        step_name: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.step_name = step_name
        if step_name:
            message = f"Step '{step_name}' timed out after {timeout_seconds}s"
        else:
            message = f"Workflow timed out after {timeout_seconds}s"
        super().__init__(message, workflow_name)

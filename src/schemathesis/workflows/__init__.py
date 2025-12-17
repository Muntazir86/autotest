"""Workflow Definitions Module for Schemathesis.

This module provides:
- Declarative YAML workflow definitions
- CRUD sequence testing
- Multi-step API test scenarios
- Data flow between steps
- Conditional execution and loops
"""

from __future__ import annotations

from schemathesis.workflows.models import (
    Workflow,
    WorkflowStep,
    RequestConfig,
    ExpectConfig,
    LoopConfig,
    PollConfig,
    WorkflowSettings,
    WorkflowResult,
    StepResult,
    StepStatus,
    FailureAction,
)
from schemathesis.workflows.parser import WorkflowParser
from schemathesis.workflows.executor import WorkflowExecutor
from schemathesis.workflows.expressions import ExpressionEngine
from schemathesis.workflows.dependency_graph import DependencyGraph
from schemathesis.workflows.validator import ResponseValidator
from schemathesis.workflows.errors import (
    WorkflowError,
    WorkflowParseError,
    WorkflowExecutionError,
    WorkflowValidationError,
    CircularDependencyError,
    StepExecutionError,
    ExpressionError,
)
from schemathesis.workflows.generator import WorkflowGenerator
from schemathesis.workflows.reporting import WorkflowReportGenerator, generate_workflow_report
from schemathesis.workflows.templates import get_template as get_workflow_template, list_templates as list_workflow_templates

__all__ = [
    # Models
    "Workflow",
    "WorkflowStep",
    "RequestConfig",
    "ExpectConfig",
    "LoopConfig",
    "PollConfig",
    "WorkflowSettings",
    "WorkflowResult",
    "StepResult",
    "StepStatus",
    "FailureAction",
    # Core components
    "WorkflowParser",
    "WorkflowExecutor",
    "ExpressionEngine",
    "DependencyGraph",
    "ResponseValidator",
    # Errors
    "WorkflowError",
    "WorkflowParseError",
    "WorkflowExecutionError",
    "WorkflowValidationError",
    "CircularDependencyError",
    "StepExecutionError",
    "ExpressionError",
    # Generator
    "WorkflowGenerator",
    # Reporting
    "WorkflowReportGenerator",
    "generate_workflow_report",
    # Templates
    "get_workflow_template",
    "list_workflow_templates",
]

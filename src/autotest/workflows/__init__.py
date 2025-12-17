"""Workflow Definitions Module for Autotest.

This module provides:
- Declarative YAML workflow definitions
- CRUD sequence testing
- Multi-step API test scenarios
- Data flow between steps
- Conditional execution and loops
"""

from __future__ import annotations

from autotest.workflows.models import (
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
from autotest.workflows.parser import WorkflowParser
from autotest.workflows.executor import WorkflowExecutor
from autotest.workflows.expressions import ExpressionEngine
from autotest.workflows.dependency_graph import DependencyGraph
from autotest.workflows.validator import ResponseValidator
from autotest.workflows.errors import (
    WorkflowError,
    WorkflowParseError,
    WorkflowExecutionError,
    WorkflowValidationError,
    CircularDependencyError,
    StepExecutionError,
    ExpressionError,
)
from autotest.workflows.generator import WorkflowGenerator
from autotest.workflows.reporting import WorkflowReportGenerator, generate_workflow_report
from autotest.workflows.templates import get_template as get_workflow_template, list_templates as list_workflow_templates

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

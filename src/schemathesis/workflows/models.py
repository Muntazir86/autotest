"""Data models for workflow definitions.

These models represent the structure of workflow YAML files and execution results.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FailureAction(str, Enum):
    """Action to take when a step fails."""

    ABORT = "abort"
    CONTINUE = "continue"
    RETRY = "retry"


class StepStatus(str, Enum):
    """Status of a workflow step execution."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERRORED = "errored"


class RequestConfig(BaseModel):
    """Request configuration for a workflow step."""

    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, Any] = Field(default_factory=dict)
    path: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    body_file: str | None = None
    form: dict[str, Any] | None = None
    content_type: str | None = None

    model_config = {"extra": "forbid"}


class ExpectBodyConfig(BaseModel):
    """Body expectation configuration."""

    model_config = {"extra": "allow"}


class ExpectConfig(BaseModel):
    """Expectation configuration for a workflow step."""

    status: list[int] = Field(default_factory=lambda: [200])
    headers: dict[str, Any] = Field(default_factory=dict)
    body: dict[str, Any] = Field(default_factory=dict)
    response_time_ms: int | None = None
    schema: bool = False
    custom: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class RetryConfig(BaseModel):
    """Retry configuration for a workflow step."""

    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0

    model_config = {"extra": "forbid"}


class LoopConfig(BaseModel):
    """Loop configuration for a workflow step."""

    count: int | None = None
    over: str | None = None
    as_var: str = "item"
    until: str | None = None
    delay: float | None = None

    model_config = {"extra": "forbid"}


class PollUntilConfig(BaseModel):
    """Polling until condition configuration."""

    body: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class PollWhileConfig(BaseModel):
    """Polling while condition configuration."""

    body: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class PollConfig(BaseModel):
    """Polling configuration for async operations."""

    interval: float = 5.0
    timeout: float = 60.0
    initial_delay: float = 0.0
    until: PollUntilConfig | None = None
    while_condition: PollWhileConfig | None = Field(default=None, alias="while")
    on_timeout: str = "fail"

    model_config = {"extra": "forbid", "populate_by_name": True}


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    name: str
    endpoint: str
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    condition: str | None = None
    request: RequestConfig = Field(default_factory=RequestConfig)
    expect: ExpectConfig = Field(default_factory=ExpectConfig)
    extract: dict[str, str] = Field(default_factory=dict)
    on_failure: FailureAction = FailureAction.ABORT
    retry: RetryConfig | None = None
    timeout: float | None = None
    loop: LoopConfig | None = None
    poll: PollConfig | None = None
    ignore_failure: bool = False
    variables: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    def get_method_and_path(self) -> tuple[str, str]:
        """Parse the endpoint string into method and path."""
        parts = self.endpoint.split(maxsplit=1)
        if len(parts) == 2:
            return parts[0].upper(), parts[1]
        elif len(parts) == 1:
            return "GET", parts[0]
        return "GET", "/"


class WorkflowSettings(BaseModel):
    """Settings for workflow execution."""

    timeout: int = 300
    retry_failed_steps: int = 0
    parallel_steps: bool = False

    model_config = {"extra": "forbid"}


class Workflow(BaseModel):
    """A complete workflow definition."""

    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    setup: list[WorkflowStep] = Field(default_factory=list)
    steps: list[WorkflowStep] = Field(default_factory=list)
    teardown: list[WorkflowStep] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    def get_all_step_names(self) -> set[str]:
        """Get all step names in the workflow."""
        names = set()
        for step in self.setup + self.steps + self.teardown:
            names.add(step.name)
        return names


@dataclass
class StepResult:
    """Result of executing a single workflow step."""

    step_name: str
    status: StepStatus
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float = 0.0
    request_method: str | None = None
    request_url: str | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: Any = None
    response_status: int | None = None
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: Any = None
    response_time_ms: float | None = None
    extracted_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    check_results: list[dict[str, Any]] = field(default_factory=list)
    loop_iteration: int | None = None
    poll_attempts: int | None = None

    def finish(self, status: StepStatus, error_message: str | None = None) -> None:
        """Mark the step as finished."""
        self.end_time = datetime.utcnow()
        self.status = status
        self.error_message = error_message
        if self.start_time and self.end_time:
            self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() + "Z" if self.start_time else None,
            "end_time": self.end_time.isoformat() + "Z" if self.end_time else None,
            "duration_ms": round(self.duration_ms, 2),
            "request": {
                "method": self.request_method,
                "url": self.request_url,
                "headers": self.request_headers,
                "body": self.request_body,
            },
            "response": {
                "status": self.response_status,
                "headers": self.response_headers,
                "body": self.response_body,
                "response_time_ms": round(self.response_time_ms, 2) if self.response_time_ms else None,
            },
            "extracted_data": self.extracted_data,
            "error_message": self.error_message,
            "check_results": self.check_results,
            "loop_iteration": self.loop_iteration,
            "poll_attempts": self.poll_attempts,
        }


@dataclass
class WorkflowResult:
    """Result of executing a complete workflow."""

    workflow_name: str
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: StepStatus = StepStatus.PENDING
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    setup_results: list[StepResult] = field(default_factory=list)
    step_results: list[StepResult] = field(default_factory=list)
    teardown_results: list[StepResult] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    @property
    def total_steps(self) -> int:
        """Total number of steps executed."""
        return len(self.setup_results) + len(self.step_results) + len(self.teardown_results)

    @property
    def passed_steps(self) -> int:
        """Number of passed steps."""
        return sum(
            1
            for r in self.setup_results + self.step_results + self.teardown_results
            if r.status == StepStatus.PASSED
        )

    @property
    def failed_steps(self) -> int:
        """Number of failed steps."""
        return sum(
            1
            for r in self.setup_results + self.step_results + self.teardown_results
            if r.status == StepStatus.FAILED
        )

    @property
    def skipped_steps(self) -> int:
        """Number of skipped steps."""
        return sum(
            1
            for r in self.setup_results + self.step_results + self.teardown_results
            if r.status == StepStatus.SKIPPED
        )

    def finish(self, status: StepStatus, error_message: str | None = None) -> None:
        """Mark the workflow as finished."""
        self.end_time = datetime.utcnow()
        self.status = status
        self.error_message = error_message
        if self.start_time and self.end_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def add_setup_result(self, result: StepResult) -> None:
        """Add a setup step result."""
        self.setup_results.append(result)

    def add_step_result(self, result: StepResult) -> None:
        """Add a main step result."""
        self.step_results.append(result)

    def add_teardown_result(self, result: StepResult) -> None:
        """Add a teardown step result."""
        self.teardown_results.append(result)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_name": self.workflow_name,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() + "Z" if self.start_time else None,
            "end_time": self.end_time.isoformat() + "Z" if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "setup_results": [r.to_dict() for r in self.setup_results],
            "step_results": [r.to_dict() for r in self.step_results],
            "teardown_results": [r.to_dict() for r in self.teardown_results],
            "variables": self.variables,
            "error_message": self.error_message,
        }


class WorkflowFile(BaseModel):
    """A workflow file containing one or more workflows."""

    workflows: list[Workflow] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

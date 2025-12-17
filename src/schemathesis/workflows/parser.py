"""Workflow parser for YAML workflow definitions.

Parses workflow YAML files into workflow models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from schemathesis.workflows.errors import WorkflowParseError, WorkflowValidationError
from schemathesis.workflows.models import (
    Workflow,
    WorkflowFile,
    WorkflowStep,
    WorkflowSettings,
    RequestConfig,
    ExpectConfig,
    LoopConfig,
    PollConfig,
    RetryConfig,
    FailureAction,
)
from schemathesis.workflows.dependency_graph import DependencyGraph


class WorkflowParser:
    """Parses workflow YAML files."""

    def __init__(self) -> None:
        """Initialize the parser."""
        pass

    def parse_file(self, path: str | Path) -> WorkflowFile:
        """Parse a workflow file.

        Args:
            path: Path to the workflow YAML file.

        Returns:
            Parsed WorkflowFile object.

        Raises:
            WorkflowParseError: If parsing fails.
        """
        path = Path(path)

        if not path.exists():
            raise WorkflowParseError(f"Workflow file not found: {path}", file_path=str(path))

        try:
            content = path.read_text(encoding="utf-8")
            return self.parse_string(content, file_path=str(path))
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML: {e}", file_path=str(path))
        except Exception as e:
            if isinstance(e, (WorkflowParseError, WorkflowValidationError)):
                raise
            raise WorkflowParseError(str(e), file_path=str(path))

    def parse_string(self, content: str, file_path: str | None = None) -> WorkflowFile:
        """Parse workflow content from a string.

        Args:
            content: YAML content string.
            file_path: Optional file path for error reporting.

        Returns:
            Parsed WorkflowFile object.
        """
        try:
            data = yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise WorkflowParseError(f"Invalid YAML: {e}", file_path=file_path)

        return self.parse_dict(data, file_path=file_path)

    def parse_dict(self, data: dict[str, Any], file_path: str | None = None) -> WorkflowFile:
        """Parse workflow data from a dictionary.

        Args:
            data: Workflow data dictionary.
            file_path: Optional file path for error reporting.

        Returns:
            Parsed WorkflowFile object.
        """
        workflows: list[Workflow] = []
        global_variables = data.get("variables", {})

        workflows_data = data.get("workflows", [])
        if not isinstance(workflows_data, list):
            raise WorkflowParseError("'workflows' must be a list", file_path=file_path)

        for i, workflow_data in enumerate(workflows_data):
            try:
                workflow = self._parse_workflow(workflow_data, global_variables)
                self._validate_workflow(workflow)
                workflows.append(workflow)
            except WorkflowParseError:
                raise
            except WorkflowValidationError:
                raise
            except Exception as e:
                workflow_name = workflow_data.get("name", f"workflow[{i}]")
                raise WorkflowParseError(str(e), workflow_name=workflow_name, file_path=file_path)

        return WorkflowFile(workflows=workflows, variables=global_variables)

    def _parse_workflow(self, data: dict[str, Any], global_variables: dict[str, Any]) -> Workflow:
        """Parse a single workflow definition."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Workflow must be a dictionary")

        name = data.get("name")
        if not name:
            raise WorkflowParseError("Workflow must have a 'name'")

        # Merge global and workflow variables
        variables = {**global_variables, **data.get("variables", {})}

        # Parse settings
        settings_data = data.get("settings", {})
        settings = WorkflowSettings(**settings_data) if settings_data else WorkflowSettings()

        # Parse steps
        setup_steps = [self._parse_step(s, name) for s in data.get("setup", [])]
        main_steps = [self._parse_step(s, name) for s in data.get("steps", [])]
        teardown_steps = [self._parse_step(s, name) for s in data.get("teardown", [])]

        return Workflow(
            name=name,
            description=data.get("description"),
            tags=data.get("tags", []),
            variables=variables,
            settings=settings,
            setup=setup_steps,
            steps=main_steps,
            teardown=teardown_steps,
        )

    def _parse_step(self, data: dict[str, Any], workflow_name: str) -> WorkflowStep:
        """Parse a single workflow step."""
        if not isinstance(data, dict):
            raise WorkflowParseError("Step must be a dictionary", workflow_name=workflow_name)

        name = data.get("name")
        if not name:
            raise WorkflowParseError("Step must have a 'name'", workflow_name=workflow_name)

        endpoint = data.get("endpoint")
        if not endpoint:
            raise WorkflowParseError(f"Step '{name}' must have an 'endpoint'", workflow_name=workflow_name)

        # Parse request config
        request_data = data.get("request", {})
        request = RequestConfig(**request_data) if request_data else RequestConfig()

        # Parse expect config
        expect_data = data.get("expect", {})
        expect = ExpectConfig(**expect_data) if expect_data else ExpectConfig()

        # Parse loop config
        loop_data = data.get("loop")
        loop = None
        if loop_data:
            # Handle 'as' keyword which is reserved in Python
            if "as" in loop_data:
                loop_data["as_var"] = loop_data.pop("as")
            loop = LoopConfig(**loop_data)

        # Parse poll config
        poll_data = data.get("poll")
        poll = None
        if poll_data:
            poll = PollConfig(**poll_data)

        # Parse retry config
        retry_data = data.get("retry")
        retry = None
        if retry_data:
            retry = RetryConfig(**retry_data)

        # Parse failure action
        on_failure_str = data.get("on_failure", "abort")
        try:
            on_failure = FailureAction(on_failure_str)
        except ValueError:
            raise WorkflowParseError(
                f"Invalid on_failure value: {on_failure_str}",
                workflow_name=workflow_name,
            )

        return WorkflowStep(
            name=name,
            endpoint=endpoint,
            description=data.get("description"),
            depends_on=data.get("depends_on", []),
            condition=data.get("condition"),
            request=request,
            expect=expect,
            extract=data.get("extract", {}),
            on_failure=on_failure,
            retry=retry,
            timeout=data.get("timeout"),
            loop=loop,
            poll=poll,
            ignore_failure=data.get("ignore_failure", False),
            variables=data.get("variables", {}),
        )

    def _validate_workflow(self, workflow: Workflow) -> None:
        """Validate a parsed workflow."""
        # Check for duplicate step names
        all_steps = workflow.setup + workflow.steps + workflow.teardown
        step_names = set()
        for step in all_steps:
            if step.name in step_names:
                raise WorkflowValidationError(
                    f"Duplicate step name: {step.name}",
                    workflow_name=workflow.name,
                )
            step_names.add(step.name)

        # Validate dependencies exist and no cycles
        graph = DependencyGraph(workflow.name)
        graph.add_steps(workflow.steps)
        graph.validate()

        # Validate step configurations
        for step in all_steps:
            self._validate_step(step, workflow.name)

    def _validate_step(self, step: WorkflowStep, workflow_name: str) -> None:
        """Validate a single step configuration."""
        # Validate endpoint format
        method, path = step.get_method_and_path()
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        if method not in valid_methods:
            raise WorkflowValidationError(
                f"Invalid HTTP method: {method}",
                workflow_name=workflow_name,
                step_name=step.name,
                field="endpoint",
            )

        # Validate loop config
        if step.loop:
            if step.loop.count is None and step.loop.over is None:
                raise WorkflowValidationError(
                    "Loop must have either 'count' or 'over'",
                    workflow_name=workflow_name,
                    step_name=step.name,
                    field="loop",
                )

        # Validate poll config
        if step.poll:
            if step.poll.interval <= 0:
                raise WorkflowValidationError(
                    "Poll interval must be positive",
                    workflow_name=workflow_name,
                    step_name=step.name,
                    field="poll.interval",
                )
            if step.poll.timeout <= 0:
                raise WorkflowValidationError(
                    "Poll timeout must be positive",
                    workflow_name=workflow_name,
                    step_name=step.name,
                    field="poll.timeout",
                )

    def load_workflows_from_directory(
        self,
        directory: str | Path,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> list[Workflow]:
        """Load all workflows from a directory.

        Args:
            directory: Path to the workflows directory.
            include: List of workflow names to include (None = all).
            exclude: List of workflow names to exclude.
            tags: List of tags to filter by (workflow must have at least one).

        Returns:
            List of parsed Workflow objects.
        """
        directory = Path(directory)

        if not directory.exists():
            raise WorkflowParseError(f"Workflows directory not found: {directory}")

        if not directory.is_dir():
            raise WorkflowParseError(f"Not a directory: {directory}")

        workflows: list[Workflow] = []

        # Find all YAML files
        yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))

        for yaml_file in sorted(yaml_files):
            try:
                workflow_file = self.parse_file(yaml_file)
                for workflow in workflow_file.workflows:
                    # Apply filters
                    if include and workflow.name not in include:
                        continue
                    if exclude and workflow.name in exclude:
                        continue
                    if tags and not any(tag in workflow.tags for tag in tags):
                        continue
                    workflows.append(workflow)
            except (WorkflowParseError, WorkflowValidationError):
                raise
            except Exception as e:
                raise WorkflowParseError(str(e), file_path=str(yaml_file))

        return workflows


def parse_workflow_file(path: str | Path) -> WorkflowFile:
    """Convenience function to parse a workflow file.

    Args:
        path: Path to the workflow YAML file.

    Returns:
        Parsed WorkflowFile object.
    """
    parser = WorkflowParser()
    return parser.parse_file(path)


def parse_workflow_string(content: str) -> WorkflowFile:
    """Convenience function to parse workflow content from a string.

    Args:
        content: YAML content string.

    Returns:
        Parsed WorkflowFile object.
    """
    parser = WorkflowParser()
    return parser.parse_string(content)

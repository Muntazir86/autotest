"""Workflow executor for running workflow definitions.

Executes workflows step by step with dependency management,
variable resolution, and result collection.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from autotest.workflows.errors import (
    StepExecutionError,
    WorkflowExecutionError,
    TimeoutError as WorkflowTimeoutError,
    ExtractionError,
)
from autotest.workflows.expressions import ExpressionEngine, extract_jsonpath
from autotest.workflows.dependency_graph import DependencyGraph
from autotest.workflows.models import (
    Workflow,
    WorkflowStep,
    WorkflowResult,
    StepResult,
    StepStatus,
    FailureAction,
)
from autotest.workflows.validator import ResponseValidator


class WorkflowExecutor:
    """Executes workflow definitions."""

    def __init__(
        self,
        base_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the executor.

        Args:
            base_url: Base URL for API requests.
            headers: Default headers for all requests.
            timeout: Default request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates.
        """
        self.base_url = base_url or ""
        self.default_headers = headers or {}
        self.default_timeout = timeout
        self.verify_ssl = verify_ssl
        self._client: httpx.Client | None = None

    def execute(
        self,
        workflow: Workflow,
        variables: dict[str, Any] | None = None,
        on_step_complete: Callable[[StepResult], None] | None = None,
    ) -> WorkflowResult:
        """Execute a workflow.

        Args:
            workflow: The workflow to execute.
            variables: Additional variables to inject.
            on_step_complete: Callback called after each step completes.

        Returns:
            WorkflowResult with execution details.
        """
        result = WorkflowResult(workflow_name=workflow.name)

        # Initialize expression engine with workflow variables
        context = {**workflow.variables, **(variables or {})}
        engine = ExpressionEngine(context)

        # Create HTTP client
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self.default_headers,
            timeout=self.default_timeout,
            verify=self.verify_ssl,
        )

        try:
            # Execute setup steps
            for step in workflow.setup:
                step_result = self._execute_step(step, engine, workflow.name)
                result.add_setup_result(step_result)
                if on_step_complete:
                    on_step_complete(step_result)

                if step_result.status == StepStatus.FAILED and not step.ignore_failure:
                    result.finish(StepStatus.FAILED, f"Setup step '{step.name}' failed")
                    return result

            # Build dependency graph and get execution order
            graph = DependencyGraph(workflow.name)
            graph.add_steps(workflow.steps)
            execution_order = graph.get_execution_order()

            # Execute main steps in order
            completed: set[str] = set()
            abort = False

            for step_name in execution_order:
                if abort:
                    # Skip remaining steps
                    step = graph.get_step(step_name)
                    if step:
                        skip_result = StepResult(
                            step_name=step_name,
                            status=StepStatus.SKIPPED,
                            start_time=datetime.utcnow(),
                        )
                        skip_result.finish(StepStatus.SKIPPED, "Skipped due to previous failure")
                        result.add_step_result(skip_result)
                    continue

                step = graph.get_step(step_name)
                if not step:
                    continue

                step_result = self._execute_step(step, engine, workflow.name)
                result.add_step_result(step_result)
                if on_step_complete:
                    on_step_complete(step_result)

                if step_result.status == StepStatus.PASSED:
                    completed.add(step_name)
                elif step_result.status == StepStatus.FAILED:
                    if step.on_failure == FailureAction.ABORT and not step.ignore_failure:
                        abort = True
                        result.error_message = f"Step '{step_name}' failed"
                    elif step.ignore_failure:
                        completed.add(step_name)

            # Execute teardown steps (always run)
            for step in workflow.teardown:
                step_result = self._execute_step(step, engine, workflow.name)
                result.add_teardown_result(step_result)
                if on_step_complete:
                    on_step_complete(step_result)

            # Determine final status
            if abort or result.failed_steps > 0:
                result.finish(StepStatus.FAILED, result.error_message)
            else:
                result.finish(StepStatus.PASSED)

            # Store final variables
            result.variables = engine.context.copy()

        except Exception as e:
            result.finish(StepStatus.ERRORED, str(e))
        finally:
            if self._client:
                self._client.close()
                self._client = None

        return result

    def _execute_step(
        self,
        step: WorkflowStep,
        engine: ExpressionEngine,
        workflow_name: str,
    ) -> StepResult:
        """Execute a single workflow step.

        Args:
            step: The step to execute.
            engine: Expression engine for variable resolution.
            workflow_name: Name of the workflow for error reporting.

        Returns:
            StepResult with execution details.
        """
        result = StepResult(
            step_name=step.name,
            status=StepStatus.RUNNING,
            start_time=datetime.utcnow(),
        )

        try:
            # Check condition
            if step.condition:
                try:
                    condition_result = engine.evaluate(step.condition, workflow_name, step.name)
                    if not self._evaluate_condition(condition_result):
                        result.finish(StepStatus.SKIPPED, "Condition not met")
                        return result
                except Exception as e:
                    # If condition evaluation fails, skip the step
                    result.finish(StepStatus.SKIPPED, f"Condition evaluation failed: {e}")
                    return result

            # Add step-level variables to context
            if step.variables:
                resolved_vars = engine.evaluate(step.variables, workflow_name, step.name)
                engine.update_context(resolved_vars)

            # Handle loop
            if step.loop:
                return self._execute_loop(step, engine, workflow_name, result)

            # Handle poll
            if step.poll:
                return self._execute_poll(step, engine, workflow_name, result)

            # Execute single request
            return self._execute_request(step, engine, workflow_name, result)

        except Exception as e:
            result.finish(StepStatus.ERRORED, str(e))
            return result

    def _execute_request(
        self,
        step: WorkflowStep,
        engine: ExpressionEngine,
        workflow_name: str,
        result: StepResult,
    ) -> StepResult:
        """Execute a single HTTP request."""
        method, path = step.get_method_and_path()

        # Resolve path variables
        resolved_path = engine.evaluate(path, workflow_name, step.name)

        # Build request
        headers = {**self.default_headers}
        if step.request.headers:
            resolved_headers = engine.evaluate(step.request.headers, workflow_name, step.name)
            headers.update(resolved_headers)

        params = None
        if step.request.query:
            params = engine.evaluate(step.request.query, workflow_name, step.name)

        body = None
        if step.request.body is not None:
            body = engine.evaluate(step.request.body, workflow_name, step.name)
        elif step.request.body_file:
            body_file_path = engine.evaluate(step.request.body_file, workflow_name, step.name)
            body = Path(body_file_path).read_text(encoding="utf-8")

        # Set content type if specified
        if step.request.content_type:
            headers["Content-Type"] = step.request.content_type

        # Build URL
        url = resolved_path
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Record request details
        result.request_method = method
        result.request_url = url
        result.request_headers = headers.copy()
        result.request_body = body

        # Execute request
        timeout = step.timeout or self.default_timeout

        try:
            start_time = time.time()
            response = self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=body if isinstance(body, (dict, list)) else None,
                content=body if isinstance(body, (str, bytes)) else None,
                timeout=timeout,
            )
            response_time_ms = (time.time() - start_time) * 1000

            # Record response details
            result.response_status = response.status_code
            result.response_headers = dict(response.headers)
            result.response_time_ms = response_time_ms

            # Parse response body
            try:
                result.response_body = response.json()
            except Exception:
                result.response_body = response.text

            # Set response in engine context for extraction
            engine.set_response_data({
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": result.response_body,
            })

            # Validate response
            validator = ResponseValidator(workflow_name, step.name)
            errors = validator.validate(
                response.status_code,
                dict(response.headers),
                result.response_body,
                response_time_ms,
                step.expect.model_dump(),
            )

            if errors:
                result.check_results = [
                    {"name": e.expectation, "status": "failed", "message": str(e)}
                    for e in errors
                ]
                result.finish(StepStatus.FAILED, errors[0].message)
            else:
                # Extract data
                if step.extract:
                    extracted = self._extract_data(step.extract, result.response_body, workflow_name, step.name)
                    result.extracted_data = extracted
                    engine.update_context(extracted)

                # Store step data for reference by other steps
                engine.set_step_data(step.name, {
                    "response": {
                        "status": response.status_code,
                        "headers": dict(response.headers),
                        "body": result.response_body,
                    },
                    "extracted": result.extracted_data,
                })

                result.finish(StepStatus.PASSED)

            # Clear response context
            engine.clear_response_data()

        except httpx.TimeoutException:
            result.finish(StepStatus.FAILED, f"Request timed out after {timeout}s")
        except httpx.RequestError as e:
            result.finish(StepStatus.ERRORED, f"Request failed: {e}")

        return result

    def _execute_loop(
        self,
        step: WorkflowStep,
        engine: ExpressionEngine,
        workflow_name: str,
        result: StepResult,
    ) -> StepResult:
        """Execute a step with loop configuration."""
        loop = step.loop
        collected_values: dict[str, list[Any]] = {key: [] for key in step.extract.keys()}
        iteration = 0

        if loop.count is not None:
            # Fixed count loop
            for i in range(loop.count):
                engine.set_variable(loop.as_var, i)
                iteration = i

                iter_result = self._execute_request(step, engine, workflow_name, result)

                # Collect extracted values
                for key, value in iter_result.extracted_data.items():
                    collected_values[key].append(value)

                if iter_result.status == StepStatus.FAILED:
                    if loop.until:
                        # Check if until condition is met
                        try:
                            until_result = engine.evaluate(loop.until, workflow_name, step.name)
                            if self._evaluate_condition(until_result):
                                break
                        except Exception:
                            pass
                    result.finish(StepStatus.FAILED, iter_result.error_message)
                    return result

                # Check until condition
                if loop.until:
                    try:
                        until_result = engine.evaluate(loop.until, workflow_name, step.name)
                        if self._evaluate_condition(until_result):
                            break
                    except Exception:
                        pass

                # Delay between iterations
                if loop.delay and i < loop.count - 1:
                    time.sleep(loop.delay)

        elif loop.over:
            # Loop over array
            items = engine.evaluate(loop.over, workflow_name, step.name)
            if not isinstance(items, list):
                items = [items]

            for i, item in enumerate(items):
                engine.set_variable(loop.as_var, item)
                iteration = i

                iter_result = self._execute_request(step, engine, workflow_name, result)

                # Collect extracted values
                for key, value in iter_result.extracted_data.items():
                    collected_values[key].append(value)

                if iter_result.status == StepStatus.FAILED:
                    result.finish(StepStatus.FAILED, iter_result.error_message)
                    return result

                # Delay between iterations
                if loop.delay and i < len(items) - 1:
                    time.sleep(loop.delay)

        # Store collected values
        result.extracted_data = {key: values for key, values in collected_values.items()}
        engine.update_context(result.extracted_data)
        result.loop_iteration = iteration
        result.finish(StepStatus.PASSED)
        return result

    def _execute_poll(
        self,
        step: WorkflowStep,
        engine: ExpressionEngine,
        workflow_name: str,
        result: StepResult,
    ) -> StepResult:
        """Execute a step with polling configuration."""
        poll = step.poll
        start_time = time.time()
        attempts = 0

        # Initial delay
        if poll.initial_delay > 0:
            time.sleep(poll.initial_delay)

        while True:
            attempts += 1
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed >= poll.timeout:
                if poll.on_timeout == "fail":
                    result.poll_attempts = attempts
                    result.finish(StepStatus.FAILED, f"Polling timed out after {poll.timeout}s")
                else:
                    result.poll_attempts = attempts
                    result.finish(StepStatus.PASSED, "Polling timed out (continuing)")
                return result

            # Execute request
            iter_result = self._execute_request(step, engine, workflow_name, result)

            if iter_result.status == StepStatus.ERRORED:
                result.poll_attempts = attempts
                result.finish(StepStatus.ERRORED, iter_result.error_message)
                return result

            # Check until condition
            if poll.until:
                if self._check_poll_condition(poll.until.body, iter_result.response_body):
                    result.poll_attempts = attempts
                    result.finish(StepStatus.PASSED)
                    return result

            # Check while condition
            if poll.while_condition:
                if not self._check_poll_condition(poll.while_condition.body, iter_result.response_body):
                    result.poll_attempts = attempts
                    result.finish(StepStatus.PASSED)
                    return result

            # Wait before next poll
            time.sleep(poll.interval)

    def _check_poll_condition(self, condition: dict[str, Any], body: Any) -> bool:
        """Check if a polling condition is met."""
        for key, expected in condition.items():
            if isinstance(body, dict):
                actual = body.get(key)
            else:
                actual = None

            if isinstance(expected, list):
                # Any of the values
                if actual in expected:
                    return True
            elif actual == expected:
                return True

        return False

    def _extract_data(
        self,
        extract_config: dict[str, str],
        body: Any,
        workflow_name: str,
        step_name: str,
    ) -> dict[str, Any]:
        """Extract data from response body using JSONPath."""
        extracted: dict[str, Any] = {}

        for var_name, path in extract_config.items():
            try:
                value = extract_jsonpath(body, path)
                extracted[var_name] = value
            except Exception as e:
                raise ExtractionError(path, str(e), workflow_name, step_name)

        return extracted

    def _evaluate_condition(self, value: Any) -> bool:
        """Evaluate a condition value as boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() not in ("false", "0", "no", "null", "none", "")
        if value is None:
            return False
        return bool(value)


def run_workflow(
    workflow: Workflow,
    base_url: str,
    headers: dict[str, str] | None = None,
    variables: dict[str, Any] | None = None,
) -> WorkflowResult:
    """Convenience function to run a workflow.

    Args:
        workflow: The workflow to execute.
        base_url: Base URL for API requests.
        headers: Default headers for all requests.
        variables: Additional variables to inject.

    Returns:
        WorkflowResult with execution details.
    """
    executor = WorkflowExecutor(base_url=base_url, headers=headers)
    return executor.execute(workflow, variables=variables)

"""CLI commands for workflow management and execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from schemathesis.cli.ext.groups import StyledGroup


@click.group(name="workflow", cls=StyledGroup)
def workflow_group() -> None:
    """Manage and execute workflow definitions."""
    pass


@workflow_group.command(name="run")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--base-url",
    "-b",
    type=str,
    help="Base URL for API requests",
)
@click.option(
    "--header",
    "-H",
    multiple=True,
    help="Request header (format: 'Name: Value')",
)
@click.option(
    "--tags",
    "-t",
    multiple=True,
    help="Run only workflows with these tags",
)
@click.option(
    "--name",
    "-n",
    multiple=True,
    help="Run only workflows with these names",
)
@click.option(
    "--var",
    "-v",
    multiple=True,
    help="Variable to inject (format: 'name=value')",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for results (JSON)",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show detailed output",
)
def run_workflow(
    path: str,
    base_url: str | None,
    header: tuple[str, ...],
    tags: tuple[str, ...],
    name: tuple[str, ...],
    var: tuple[str, ...],
    output: str | None,
    verbose: bool,
) -> None:
    """Run workflow definitions from a file or directory."""
    from schemathesis.workflows import WorkflowParser, WorkflowExecutor, StepStatus

    path_obj = Path(path)

    # Parse headers
    headers: dict[str, str] = {}
    for h in header:
        if ":" in h:
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

    # Parse variables
    variables: dict[str, Any] = {}
    for v in var:
        if "=" in v:
            key, value = v.split("=", 1)
            variables[key.strip()] = value.strip()

    # Load workflows
    parser = WorkflowParser()

    try:
        if path_obj.is_dir():
            workflows = parser.load_workflows_from_directory(
                path_obj,
                include=list(name) if name else None,
                tags=list(tags) if tags else None,
            )
        else:
            workflow_file = parser.parse_file(path_obj)
            workflows = workflow_file.workflows

            # Filter by name and tags
            if name:
                workflows = [w for w in workflows if w.name in name]
            if tags:
                workflows = [w for w in workflows if any(t in w.tags for t in tags)]

    except Exception as e:
        click.secho(f"❌ Failed to load workflows: {e}", fg="red")
        raise SystemExit(1)

    if not workflows:
        click.secho("No workflows found matching criteria", fg="yellow")
        raise SystemExit(0)

    click.echo(f"Found {len(workflows)} workflow(s) to run")

    # Check base_url
    if not base_url:
        click.secho("❌ Base URL is required. Use --base-url option.", fg="red")
        raise SystemExit(1)

    # Execute workflows
    executor = WorkflowExecutor(base_url=base_url, headers=headers)
    results = []
    total_passed = 0
    total_failed = 0

    for workflow in workflows:
        click.echo(f"\n{'='*60}")
        click.echo(f"Running workflow: {workflow.name}")
        if workflow.description:
            click.echo(f"  {workflow.description}")
        click.echo(f"{'='*60}")

        def on_step_complete(step_result: Any) -> None:
            if verbose:
                status_color = {
                    StepStatus.PASSED: "green",
                    StepStatus.FAILED: "red",
                    StepStatus.SKIPPED: "yellow",
                    StepStatus.ERRORED: "red",
                }.get(step_result.status, "white")

                click.secho(
                    f"  [{step_result.status.value.upper()}] {step_result.step_name}",
                    fg=status_color,
                )
                if step_result.error_message and step_result.status != StepStatus.PASSED:
                    click.echo(f"    Error: {step_result.error_message}")

        result = executor.execute(
            workflow,
            variables=variables,
            on_step_complete=on_step_complete if verbose else None,
        )
        results.append(result)

        # Summary for this workflow
        if result.status == StepStatus.PASSED:
            total_passed += 1
            click.secho(f"\n✅ Workflow PASSED", fg="green")
        else:
            total_failed += 1
            click.secho(f"\n❌ Workflow FAILED", fg="red")
            if result.error_message:
                click.echo(f"   {result.error_message}")

        click.echo(f"   Steps: {result.passed_steps} passed, {result.failed_steps} failed, {result.skipped_steps} skipped")
        click.echo(f"   Duration: {result.duration_seconds:.2f}s")

    # Overall summary
    click.echo(f"\n{'='*60}")
    click.echo("SUMMARY")
    click.echo(f"{'='*60}")
    click.echo(f"Workflows: {total_passed} passed, {total_failed} failed")

    # Save results if output specified
    if output:
        import json

        output_data = {
            "total_workflows": len(results),
            "passed": total_passed,
            "failed": total_failed,
            "results": [r.to_dict() for r in results],
        }
        Path(output).write_text(json.dumps(output_data, indent=2, default=str), encoding="utf-8")
        click.echo(f"\nResults saved to: {output}")

    if total_failed > 0:
        raise SystemExit(1)


@workflow_group.command(name="list")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--tags",
    "-t",
    multiple=True,
    help="Filter by tags",
)
def list_workflows(path: str, tags: tuple[str, ...]) -> None:
    """List available workflows in a file or directory."""
    from schemathesis.workflows import WorkflowParser

    path_obj = Path(path)
    parser = WorkflowParser()

    try:
        if path_obj.is_dir():
            workflows = parser.load_workflows_from_directory(
                path_obj,
                tags=list(tags) if tags else None,
            )
        else:
            workflow_file = parser.parse_file(path_obj)
            workflows = workflow_file.workflows
            if tags:
                workflows = [w for w in workflows if any(t in w.tags for t in tags)]

    except Exception as e:
        click.secho(f"❌ Failed to load workflows: {e}", fg="red")
        raise SystemExit(1)

    if not workflows:
        click.echo("No workflows found")
        return

    click.echo(f"Found {len(workflows)} workflow(s):\n")

    for workflow in workflows:
        click.secho(f"• {workflow.name}", fg="cyan", bold=True)
        if workflow.description:
            click.echo(f"  {workflow.description}")
        if workflow.tags:
            click.echo(f"  Tags: {', '.join(workflow.tags)}")
        click.echo(f"  Steps: {len(workflow.setup)} setup, {len(workflow.steps)} main, {len(workflow.teardown)} teardown")
        click.echo()


@workflow_group.command(name="validate")
@click.argument("path", type=click.Path(exists=True))
def validate_workflow(path: str) -> None:
    """Validate workflow definitions."""
    from schemathesis.workflows import WorkflowParser
    from schemathesis.workflows.errors import WorkflowParseError, WorkflowValidationError

    path_obj = Path(path)
    parser = WorkflowParser()

    click.echo(f"Validating: {path}")

    try:
        if path_obj.is_dir():
            workflows = parser.load_workflows_from_directory(path_obj)
        else:
            workflow_file = parser.parse_file(path_obj)
            workflows = workflow_file.workflows

        click.secho(f"\n✅ All {len(workflows)} workflow(s) are valid", fg="green")

        for workflow in workflows:
            click.echo(f"  • {workflow.name}: {len(workflow.steps)} steps")

    except (WorkflowParseError, WorkflowValidationError) as e:
        click.secho(f"\n❌ Validation failed: {e}", fg="red")
        raise SystemExit(1)
    except Exception as e:
        click.secho(f"\n❌ Error: {e}", fg="red")
        raise SystemExit(1)


@workflow_group.command(name="generate")
@click.option(
    "--from-spec",
    "-s",
    type=click.Path(exists=True),
    required=True,
    help="OpenAPI specification file",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="./workflows",
    help="Output directory for generated workflows",
)
@click.option(
    "--resource",
    "-r",
    multiple=True,
    help="Generate workflow for specific resource (e.g., 'users', 'orders')",
)
def generate_workflow(from_spec: str, output: str, resource: tuple[str, ...]) -> None:
    """Generate workflow definitions from OpenAPI specification."""
    from schemathesis.workflows.generator import WorkflowGenerator

    click.echo(f"Generating workflows from: {from_spec}")

    try:
        generator = WorkflowGenerator()
        workflows = generator.generate_from_spec(
            from_spec,
            resources=list(resource) if resource else None,
        )

        if not workflows:
            click.secho("No CRUD patterns detected in specification", fg="yellow")
            return

        # Create output directory
        output_path = Path(output)
        output_path.mkdir(parents=True, exist_ok=True)

        # Write workflows
        for workflow in workflows:
            file_path = output_path / f"{workflow.name}.yaml"
            generator.write_workflow(workflow, file_path)
            click.echo(f"  Created: {file_path}")

        click.secho(f"\n✅ Generated {len(workflows)} workflow(s)", fg="green")

    except Exception as e:
        click.secho(f"❌ Failed to generate workflows: {e}", fg="red")
        raise SystemExit(1)

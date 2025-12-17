"""Workflow generator for auto-generating workflows from OpenAPI specifications.

Detects CRUD patterns and generates appropriate workflow definitions.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from autotest.workflows.models import (
    Workflow,
    WorkflowStep,
    WorkflowSettings,
    RequestConfig,
    ExpectConfig,
)


class WorkflowGenerator:
    """Generates workflow definitions from OpenAPI specifications."""

    def __init__(self) -> None:
        """Initialize the generator."""
        pass

    def generate_from_spec(
        self,
        spec_path: str | Path,
        resources: list[str] | None = None,
    ) -> list[Workflow]:
        """Generate workflows from an OpenAPI specification.

        Args:
            spec_path: Path to the OpenAPI specification file.
            resources: Optional list of resource names to generate workflows for.

        Returns:
            List of generated Workflow objects.
        """
        spec_path = Path(spec_path)

        # Load the spec
        content = spec_path.read_text(encoding="utf-8")
        if spec_path.suffix in (".yaml", ".yml"):
            spec = yaml.safe_load(content)
        else:
            import json

            spec = json.loads(content)

        # Detect resources and CRUD operations
        resource_ops = self._detect_crud_operations(spec)

        # Filter by requested resources
        if resources:
            resource_ops = {k: v for k, v in resource_ops.items() if k in resources}

        # Generate workflows
        workflows = []
        for resource_name, operations in resource_ops.items():
            workflow = self._generate_crud_workflow(resource_name, operations, spec)
            if workflow:
                workflows.append(workflow)

        return workflows

    def _detect_crud_operations(self, spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Detect CRUD operations grouped by resource.

        Returns:
            Dict mapping resource names to their operations.
        """
        resources: dict[str, dict[str, Any]] = {}
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            # Skip if not a dict (could be $ref)
            if not isinstance(path_item, dict):
                continue

            # Detect resource name from path
            resource_name = self._extract_resource_name(path)
            if not resource_name:
                continue

            if resource_name not in resources:
                resources[resource_name] = {
                    "create": None,
                    "read": None,
                    "update": None,
                    "delete": None,
                    "list": None,
                    "base_path": None,
                    "item_path": None,
                }

            # Detect operation type
            has_id_param = self._has_id_parameter(path)

            for method in ["get", "post", "put", "patch", "delete"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                op_info = {
                    "method": method.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "request_body": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                    "parameters": operation.get("parameters", []),
                }

                if method == "post" and not has_id_param:
                    resources[resource_name]["create"] = op_info
                    resources[resource_name]["base_path"] = path
                elif method == "get" and has_id_param:
                    resources[resource_name]["read"] = op_info
                    resources[resource_name]["item_path"] = path
                elif method == "get" and not has_id_param:
                    resources[resource_name]["list"] = op_info
                    resources[resource_name]["base_path"] = path
                elif method in ("put", "patch") and has_id_param:
                    resources[resource_name]["update"] = op_info
                    resources[resource_name]["item_path"] = path
                elif method == "delete" and has_id_param:
                    resources[resource_name]["delete"] = op_info
                    resources[resource_name]["item_path"] = path

        # Filter out resources without any CRUD operations
        return {
            name: ops
            for name, ops in resources.items()
            if any(ops.get(op) for op in ["create", "read", "update", "delete"])
        }

    def _extract_resource_name(self, path: str) -> str | None:
        """Extract resource name from a path."""
        # Remove leading slash and split
        parts = path.strip("/").split("/")

        # Find the first non-parameter part
        for part in parts:
            if not part.startswith("{") and part:
                # Convert to singular if needed
                return self._singularize(part)

        return None

    def _singularize(self, word: str) -> str:
        """Simple singularization of a word."""
        if word.endswith("ies"):
            return word[:-3] + "y"
        elif word.endswith("es"):
            return word[:-2]
        elif word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    def _has_id_parameter(self, path: str) -> bool:
        """Check if a path has an ID parameter."""
        # Look for {id}, {userId}, {user_id}, etc.
        return bool(re.search(r"\{[^}]*id[^}]*\}", path, re.IGNORECASE))

    def _generate_crud_workflow(
        self,
        resource_name: str,
        operations: dict[str, Any],
        spec: dict[str, Any],
    ) -> Workflow | None:
        """Generate a CRUD workflow for a resource."""
        steps: list[WorkflowStep] = []
        teardown_steps: list[WorkflowStep] = []

        # Determine the ID field name
        id_field = self._detect_id_field(operations, spec)
        id_var = f"{resource_name}_id"

        # Create step
        if operations.get("create"):
            create_op = operations["create"]
            create_step = WorkflowStep(
                name=f"create_{resource_name}",
                endpoint=f"{create_op['method']} {create_op['path']}",
                description=f"Create a new {resource_name}",
                request=RequestConfig(
                    body=self._generate_sample_body(create_op, spec),
                ),
                expect=ExpectConfig(
                    status=[201, 200],
                ),
                extract={id_var: f"$.{id_field}"},
            )
            steps.append(create_step)

        # Read step
        if operations.get("read") and operations.get("create"):
            read_op = operations["read"]
            read_path = self._substitute_id_param(read_op["path"], id_var)
            read_step = WorkflowStep(
                name=f"get_{resource_name}",
                endpoint=f"{read_op['method']} {read_path}",
                description=f"Retrieve the created {resource_name}",
                depends_on=[f"create_{resource_name}"],
                expect=ExpectConfig(
                    status=[200],
                ),
            )
            steps.append(read_step)

        # Update step
        if operations.get("update") and operations.get("create"):
            update_op = operations["update"]
            update_path = self._substitute_id_param(update_op["path"], id_var)
            update_step = WorkflowStep(
                name=f"update_{resource_name}",
                endpoint=f"{update_op['method']} {update_path}",
                description=f"Update the {resource_name}",
                depends_on=[f"get_{resource_name}"] if operations.get("read") else [f"create_{resource_name}"],
                request=RequestConfig(
                    body=self._generate_sample_body(update_op, spec),
                ),
                expect=ExpectConfig(
                    status=[200],
                ),
            )
            steps.append(update_step)

        # Delete step
        if operations.get("delete") and operations.get("create"):
            delete_op = operations["delete"]
            delete_path = self._substitute_id_param(delete_op["path"], id_var)
            delete_step = WorkflowStep(
                name=f"delete_{resource_name}",
                endpoint=f"{delete_op['method']} {delete_path}",
                description=f"Delete the {resource_name}",
                depends_on=[f"update_{resource_name}"] if operations.get("update") else [f"get_{resource_name}"] if operations.get("read") else [f"create_{resource_name}"],
                expect=ExpectConfig(
                    status=[204, 200],
                ),
            )
            steps.append(delete_step)

        # Verify deletion step
        if operations.get("read") and operations.get("delete") and operations.get("create"):
            read_op = operations["read"]
            read_path = self._substitute_id_param(read_op["path"], id_var)
            verify_step = WorkflowStep(
                name=f"verify_{resource_name}_deleted",
                endpoint=f"GET {read_path}",
                description=f"Verify the {resource_name} was deleted",
                depends_on=[f"delete_{resource_name}"],
                expect=ExpectConfig(
                    status=[404],
                ),
            )
            steps.append(verify_step)

        # Teardown: cleanup if workflow fails
        if operations.get("delete") and operations.get("create"):
            delete_op = operations["delete"]
            delete_path = self._substitute_id_param(delete_op["path"], id_var)
            cleanup_step = WorkflowStep(
                name=f"cleanup_{resource_name}",
                endpoint=f"{delete_op['method']} {delete_path}",
                description=f"Cleanup: delete {resource_name} if it exists",
                condition=f"${{{id_var}}} != null",
                ignore_failure=True,
            )
            teardown_steps.append(cleanup_step)

        if not steps:
            return None

        return Workflow(
            name=f"{resource_name}_crud",
            description=f"CRUD workflow for {resource_name} resource",
            tags=["crud", resource_name, "generated"],
            settings=WorkflowSettings(timeout=300),
            steps=steps,
            teardown=teardown_steps,
        )

    def _detect_id_field(self, operations: dict[str, Any], spec: dict[str, Any]) -> str:
        """Detect the ID field name from operations."""
        # Check create response schema
        create_op = operations.get("create")
        if create_op:
            responses = create_op.get("responses", {})
            for status in ["201", "200"]:
                if status in responses:
                    schema = self._get_response_schema(responses[status], spec)
                    if schema:
                        properties = schema.get("properties", {})
                        for field in ["id", "ID", "_id", "uuid", "UUID"]:
                            if field in properties:
                                return field

        return "id"

    def _get_response_schema(self, response: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any] | None:
        """Get the schema from a response definition."""
        content = response.get("content", {})
        for media_type in ["application/json", "*/*"]:
            if media_type in content:
                schema = content[media_type].get("schema", {})
                # Resolve $ref if present
                if "$ref" in schema:
                    return self._resolve_ref(schema["$ref"], spec)
                return schema
        return None

    def _resolve_ref(self, ref: str, spec: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve a $ref to its schema."""
        if not ref.startswith("#/"):
            return None

        parts = ref[2:].split("/")
        current = spec
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current if isinstance(current, dict) else None

    def _substitute_id_param(self, path: str, id_var: str) -> str:
        """Substitute ID parameter in path with variable reference."""
        # Replace {id}, {userId}, {user_id}, etc. with ${id_var}
        return re.sub(r"\{[^}]*id[^}]*\}", f"${{{id_var}}}", path, flags=re.IGNORECASE)

    def _generate_sample_body(self, operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        """Generate a sample request body from operation schema."""
        request_body = operation.get("request_body", {})
        if not request_body:
            return {}

        content = request_body.get("content", {})
        for media_type in ["application/json", "*/*"]:
            if media_type in content:
                schema = content[media_type].get("schema", {})
                if "$ref" in schema:
                    schema = self._resolve_ref(schema["$ref"], spec) or {}
                return self._generate_sample_from_schema(schema)

        return {}

    def _generate_sample_from_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate sample data from a JSON schema."""
        if schema.get("type") != "object":
            return {}

        sample: dict[str, Any] = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            # Skip read-only properties
            if prop_schema.get("readOnly"):
                continue

            # Generate sample value
            prop_type = prop_schema.get("type", "string")

            if prop_type == "string":
                if "email" in prop_name.lower():
                    sample[prop_name] = "${faker:email}"
                elif "name" in prop_name.lower():
                    sample[prop_name] = "${faker:name}"
                elif "phone" in prop_name.lower():
                    sample[prop_name] = "${faker:phone}"
                elif "url" in prop_name.lower():
                    sample[prop_name] = "${faker:url}"
                else:
                    sample[prop_name] = f"test_{prop_name}"
            elif prop_type == "integer":
                sample[prop_name] = "${random:min=1,max=100}"
            elif prop_type == "number":
                sample[prop_name] = "${random:min=1,max=100}"
            elif prop_type == "boolean":
                sample[prop_name] = True
            elif prop_type == "array":
                sample[prop_name] = []
            elif prop_type == "object":
                sample[prop_name] = {}

        return sample

    def write_workflow(self, workflow: Workflow, path: Path) -> None:
        """Write a workflow to a YAML file."""
        data = {
            "workflows": [
                {
                    "name": workflow.name,
                    "description": workflow.description,
                    "tags": workflow.tags,
                    "settings": {
                        "timeout": workflow.settings.timeout,
                    },
                    "steps": [self._step_to_dict(step) for step in workflow.steps],
                    "teardown": [self._step_to_dict(step) for step in workflow.teardown],
                }
            ]
        }

        path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")

    def _step_to_dict(self, step: WorkflowStep) -> dict[str, Any]:
        """Convert a WorkflowStep to a dictionary for YAML output."""
        result: dict[str, Any] = {
            "name": step.name,
            "endpoint": step.endpoint,
        }

        if step.description:
            result["description"] = step.description

        if step.depends_on:
            result["depends_on"] = step.depends_on

        if step.condition:
            result["condition"] = step.condition

        if step.request.body:
            result["request"] = {"body": step.request.body}

        if step.expect.status != [200]:
            result["expect"] = {"status": step.expect.status}

        if step.extract:
            result["extract"] = step.extract

        if step.ignore_failure:
            result["ignore_failure"] = True

        return result

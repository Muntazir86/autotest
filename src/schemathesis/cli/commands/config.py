"""CLI commands for YAML configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from schemathesis.cli.ext.groups import StyledGroup


@click.group(name="config", cls=StyledGroup)
def config_group() -> None:
    """Manage YAML configuration files."""
    pass


@config_group.command(name="init")
@click.option(
    "--template",
    type=click.Choice(["basic", "enterprise", "ci-cd", "microservices"]),
    default="basic",
    help="Configuration template to use",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default="api-tester.yaml",
    help="Output file path",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing file",
)
def init_config(template: str, output: str, force: bool) -> None:
    """Initialize a new configuration file."""
    output_path = Path(output)

    if output_path.exists() and not force:
        click.secho(f"❌ File already exists: {output}", fg="red")
        click.echo("Use --force to overwrite")
        raise SystemExit(1)

    # Get template content
    template_content = _get_template(template)

    output_path.write_text(template_content, encoding="utf-8")
    click.secho(f"✅ Created configuration file: {output}", fg="green")
    click.echo(f"\nTemplate: {template}")
    click.echo("\nNext steps:")
    click.echo("  1. Edit the configuration file to match your API")
    click.echo("  2. Set required environment variables")
    click.echo("  3. Run: schemathesis run --config api-tester.yaml")


@config_group.command(name="validate")
@click.argument("config_path", type=click.Path(exists=True))
def validate_config(config_path: str) -> None:
    """Validate a configuration file."""
    from schemathesis.yaml_config import ConfigLoader, ConfigValidationError

    click.echo(f"Validating: {config_path}")

    loader = ConfigLoader()
    issues = loader.validate_file(config_path)

    errors = [i for i in issues if isinstance(i, ConfigValidationError)]
    warnings = [i for i in issues if isinstance(i, str)]

    if errors:
        click.secho(f"\n❌ {len(errors)} error(s) found:", fg="red")
        for error in errors:
            click.echo(f"  • {error}")

    if warnings:
        click.secho(f"\n⚠️  {len(warnings)} warning(s):", fg="yellow")
        for warning in warnings:
            click.echo(f"  • {warning}")

    if not errors and not warnings:
        click.secho("\n✅ Configuration is valid", fg="green")
    elif not errors:
        click.secho("\n✅ Configuration is valid (with warnings)", fg="green")
    else:
        raise SystemExit(1)


@config_group.command(name="show")
@click.argument("config_path", type=click.Path(exists=True))
@click.option(
    "--env",
    "-e",
    type=str,
    help="Environment to apply",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["yaml", "json"]),
    default="yaml",
    help="Output format",
)
def show_config(config_path: str, env: str | None, output_format: str) -> None:
    """Show resolved configuration."""
    from schemathesis.yaml_config import ConfigLoader

    loader = ConfigLoader()

    try:
        config = loader.load(config_path, env=env)
        data = config.model_dump()

        if output_format == "json":
            import json

            click.echo(json.dumps(data, indent=2, default=str))
        else:
            import yaml

            click.echo(yaml.dump(data, default_flow_style=False, sort_keys=False))

    except Exception as e:
        click.secho(f"❌ Error loading configuration: {e}", fg="red")
        raise SystemExit(1)


@config_group.command(name="environments")
@click.argument("config_path", type=click.Path(exists=True))
def list_environments(config_path: str) -> None:
    """List available environments in configuration."""
    from schemathesis.yaml_config import ConfigLoader

    loader = ConfigLoader()

    try:
        config = loader.load(config_path, resolve_variables=False, validate=False)

        if not config.environments:
            click.echo("No environments defined in configuration")
            return

        click.echo("Available environments:")
        for env_name in config.environments.keys():
            marker = " (active)" if env_name == config.environment else ""
            click.echo(f"  • {env_name}{marker}")

    except Exception as e:
        click.secho(f"❌ Error loading configuration: {e}", fg="red")
        raise SystemExit(1)


def _get_template(template_name: str) -> str:
    """Get configuration template content."""
    templates = {
        "basic": _BASIC_TEMPLATE,
        "enterprise": _ENTERPRISE_TEMPLATE,
        "ci-cd": _CICD_TEMPLATE,
        "microservices": _MICROSERVICES_TEMPLATE,
    }
    return templates.get(template_name, _BASIC_TEMPLATE)


_BASIC_TEMPLATE = '''# API Tester Configuration
config_version: "1.0"

api:
  spec:
    type: file
    path: ./openapi.yaml
  base_url: http://localhost:8080

auth:
  default: bearer
  methods:
    bearer:
      type: bearer
      token: "${env:API_TOKEN}"

generation:
  max_examples: 100
  mode: all

reporting:
  output_dir: ./reports
  html:
    enabled: true
'''

_ENTERPRISE_TEMPLATE = '''# API Tester Configuration - Enterprise
config_version: "1.0"
profile: "enterprise"

api:
  spec:
    type: url
    path: "${env:API_SPEC_URL}"
  base_url: "${env:API_BASE_URL}"
  name: "Enterprise API"

auth:
  default: oauth2
  methods:
    oauth2:
      type: oauth2
      flow: client_credentials
      token_url: "${env:OAUTH_TOKEN_URL}"
      client_id: "${env:OAUTH_CLIENT_ID}"
      client_secret: "${env:OAUTH_CLIENT_SECRET}"
      scopes:
        - read
        - write
      refresh_buffer_seconds: 60

request:
  timeout: 30
  headers:
    User-Agent: "API-Tester/1.0"
    Accept: "application/json"
  rate_limit:
    enabled: true
    requests_per_second: 10
  retry:
    enabled: true
    max_attempts: 3

generation:
  max_examples: 500
  mode: all
  phases:
    - examples
    - coverage
    - fuzzing
    - stateful

validation:
  checks:
    - not_a_server_error
    - status_code_conformance
    - content_type_conformance
    - response_schema_conformance
    - response_headers_conformance

reporting:
  output_dir: ./reports
  html:
    enabled: true
    sanitize_headers:
      - Authorization
      - X-API-Key
  junit:
    enabled: true
  json:
    enabled: true

environments:
  development:
    api:
      base_url: http://localhost:8080
    generation:
      max_examples: 10

  staging:
    api:
      base_url: https://staging-api.example.com

  production:
    api:
      base_url: https://api.example.com
    endpoints:
      methods:
        - GET
    generation:
      mode: positive

environment: "${env:TEST_ENV:development}"
'''

_CICD_TEMPLATE = '''# API Tester Configuration - CI/CD
config_version: "1.0"
profile: "ci"

api:
  spec:
    type: url
    path: "${env:API_SPEC_URL}"
  base_url: "${env:API_BASE_URL}"

auth:
  default: bearer
  methods:
    bearer:
      type: bearer
      token: "${env:API_TOKEN}"

generation:
  max_examples: 50
  mode: all

execution:
  workers: auto
  fail_fast: true

reporting:
  output_dir: ./test-results
  html:
    enabled: true
  junit:
    enabled: true
  console:
    style: simple
    color: false

workflows:
  directory: ./workflows
  tags:
    - smoke
    - critical
'''

_MICROSERVICES_TEMPLATE = '''# API Tester Configuration - Microservices
config_version: "1.0"
profile: "microservices"

request:
  timeout: 30
  headers:
    X-Correlation-ID: "${uuid}"

variables:
  user_service_url: "${env:USER_SERVICE_URL:http://users.local:8001}"
  order_service_url: "${env:ORDER_SERVICE_URL:http://orders.local:8002}"

# Note: For microservices, you may want to create separate config files
# for each service and use the extends feature

api:
  spec:
    type: file
    path: ./specs/main-service.yaml
  base_url: "${env:MAIN_SERVICE_URL:http://localhost:8080}"

auth:
  default: bearer
  methods:
    bearer:
      type: bearer
      token: "${env:API_TOKEN}"

generation:
  max_examples: 100

workflows:
  directory: ./workflows/integration
  tags:
    - integration

reporting:
  output_dir: ./reports
  html:
    enabled: true
  junit:
    enabled: true
'''

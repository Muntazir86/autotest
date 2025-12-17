"""Configuration templates for quick setup."""

from __future__ import annotations

BASIC_TEMPLATE = '''# API Tester Configuration - Basic
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

ENTERPRISE_TEMPLATE = '''# API Tester Configuration - Enterprise
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

CICD_TEMPLATE = '''# API Tester Configuration - CI/CD
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

MICROSERVICES_TEMPLATE = '''# API Tester Configuration - Microservices
config_version: "1.0"
profile: "microservices"

request:
  timeout: 30
  headers:
    X-Correlation-ID: "${uuid}"

variables:
  user_service_url: "${env:USER_SERVICE_URL:http://users.local:8001}"
  order_service_url: "${env:ORDER_SERVICE_URL:http://orders.local:8002}"

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

TEMPLATES = {
    "basic": BASIC_TEMPLATE,
    "enterprise": ENTERPRISE_TEMPLATE,
    "ci-cd": CICD_TEMPLATE,
    "microservices": MICROSERVICES_TEMPLATE,
}


def get_template(name: str) -> str:
    """Get a configuration template by name.
    
    Args:
        name: Template name (basic, enterprise, ci-cd, microservices).
        
    Returns:
        Template content as a string.
    """
    return TEMPLATES.get(name, BASIC_TEMPLATE)


def list_templates() -> list[str]:
    """List available template names."""
    return list(TEMPLATES.keys())

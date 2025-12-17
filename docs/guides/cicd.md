# CI/CD Integration Guide

Run Autotest in CI to verify your API against its schema on every change.

## Schema Access

=== "Live Schema"
    ```bash
    autotest run http://api-host:port/openapi.json --wait-for-schema 30
    ```
    Test against the schema served by your running API. The `--wait-for-schema 30` waits up to 30 seconds for the API to become available.

=== "Static Schema"
    ```bash
    autotest run ./openapi.json --url http://api-host:port
    ```
    Test using a schema file from your repository.

## GitHub Actions

The [Autotest GitHub Action](https://github.com/Autotest/action) provides the simplest integration path.

**Basic workflow:**

```yaml
name: API Tests
on: [push, pull_request]

jobs:
  api-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start services
        run: docker compose up -d
        
      - uses: Autotest/action@v2
        with:
          schema: 'http://localhost:8080/openapi.json'
          args: >-
            --header "Authorization: Bearer ${{ secrets.API_TOKEN }}"
            --report junit
          
      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: Autotest-results
          path: Autotest-report/
          
      - name: Cleanup
        if: always()
        run: docker compose down
```

## GitLab CI

Use the official Docker image for consistent environments.

**Complete workflow example:**
```yaml
stages:
  - test

api-tests:
  stage: test
  image: 
    name: Autotest/Autotest:stable
    entrypoint: [""]
  services:
    - name: your-api:latest
      alias: api
  variables:
    API_TOKEN: "your-secret-token"
  script:
    - >
      autotest run http://api:8080/openapi.json 
      --header "Authorization: Bearer $API_TOKEN"
      --wait-for-schema 60
      --report junit
  artifacts:
    when: always
    reports:
      junit: Autotest-report/junit.xml
    paths:
      - Autotest-report/
```

## Using Configuration Files

Create `autotest.toml` to avoid repeating options and maintain consistent settings:

```toml
# Authentication
headers = { Authorization = "Bearer ${API_TOKEN}" }

# Continue testing after failures to find more issues
continue-on-failure = true

# Generate reports
[reports.junit]
enabled = true
```

Then run with just:

```bash
autotest run http://localhost:8080/openapi.json
```

See the [CLI reference](../reference/cli.md#exit-codes) for the complete list of exit codes.

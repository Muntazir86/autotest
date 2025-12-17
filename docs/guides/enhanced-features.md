# Enhanced Features: HTML Reports & Smart ID Extraction

Autotest includes two powerful features for enhanced API testing:

1. **HTML Report Generator** - Generate beautiful, interactive HTML reports
2. **Smart ID Extraction** - Automatically extract and reuse resource IDs

## HTML Report Generator

Generate self-contained, interactive HTML reports with complete request/response data.

### CLI Usage

```bash
# Generate an HTML report
autotest run https://api.example.com/openapi.json \
  --report-html=./reports/api-test-report.html

# With custom title
autotest run https://api.example.com/openapi.json \
  --report-html=./reports/report.html \
  --report-html-title="My API Test Report"

# Include full details for passed tests
autotest run https://api.example.com/openapi.json \
  --report-html=./reports/report.html \
  --report-include-passed
```

### Configuration (autotest.toml)

```toml
[reports.html]
enabled = true
path = "./reports/api-test-report.html"
title = "API Test Report"
include-passed-details = false
max-body-size = 10240  # 10KB
sanitize-headers = ["Authorization", "X-API-Key"]
```

### Python API

```python
import autotest
from Autotest.reporting import enable_html_report, generate_report

# Enable HTML report generation
enable_html_report(
    output_path="./reports/api-test-report.html",
    title="My API Test Report",
    include_passed_details=False,
    max_body_size=10240,
)

# Run your tests...
schema = autotest.openapi.from_url("https://api.example.com/openapi.json")

@schema.parametrize()
def test_api(case):
    case.call_and_validate()

# Generate the report after tests complete
report_path = generate_report()
print(f"Report generated: {report_path}")
```

### Report Features

The HTML report includes:

- **Executive Summary**: Total tests, pass/fail counts, visual progress bar
- **Endpoints Overview**: Table showing statistics per endpoint
- **Failed Tests Section**: Detailed view of all failures with:
  - Full request/response data
  - Check results
  - cURL command for reproduction
- **All Tests Section**: Searchable, filterable list of all test cases
- **Interactive Features**: Collapsible sections, search, filtering by status/method

## Smart ID Extraction

Automatically extract IDs from API responses and inject them into subsequent requests.

### The Problem

Without ID extraction, Autotest generates random IDs for path parameters:

```
POST /users (body: {"name": "John"})        → 201, {"id": 123, "name": "John"}
GET  /users/{id} (id: randomly generated)  → 404 (ID doesn't exist!)
```

### The Solution

With ID extraction enabled:

```
POST /users (body: {"name": "John"})        → 201, {"id": 123, "name": "John"}
                                               ↓ Extract ID: 123
GET  /users/{id} (id: 123)                  → 200 ✓
PUT  /users/{id} (id: 123)                  → 200 ✓
DELETE /users/{id} (id: 123)                → 204 ✓
```

### CLI Usage

```bash
# Enable ID extraction
autotest run https://api.example.com/openapi.json --extract-ids

# With verbose logging
autotest run https://api.example.com/openapi.json \
  --extract-ids \
  --id-verbose

# Choose injection strategy
autotest run https://api.example.com/openapi.json \
  --extract-ids \
  --id-injection-strategy=latest  # or "random" or "first"
```

### Configuration (autotest.toml)

```toml
[id-extraction]
enabled = true
prefer = "latest"  # "latest", "random", "first"
fallback-to-generated = true
inject-into-body = true
inject-into-query = true
verbose = false

# Custom ID field patterns (regex)
custom-patterns = [
    "resourceId",
    ".*_ref"
]

# Fields to never treat as IDs
ignore-fields = [
    "created_at",
    "updated_at",
    "version"
]
```

### Python API

```python
import autotest
from Autotest.extraction import enable_id_extraction, get_extraction_summary

# Enable ID extraction
enable_id_extraction(
    prefer="latest",
    fallback_to_generated=True,
    inject_into_body=True,
    inject_into_query=True,
    verbose=True,
)

# Run your tests...
schema = autotest.openapi.from_url("https://api.example.com/openapi.json")

@schema.parametrize()
def test_api(case):
    case.call_and_validate()

# Get extraction summary
summary = get_extraction_summary()
print(f"Total IDs extracted: {summary['store']['total_ids']}")
print(f"Injections performed: {summary['injector']['total_injections']}")
```

### ID Detection Strategies

The extractor uses multiple strategies to detect IDs:

1. **Path Parameter Matching**: Matches response fields to path parameters in other endpoints
2. **Common ID Field Names**: Looks for `id`, `*_id`, `*Id`, `uuid`, etc.
3. **Schema Hints**: Uses `readOnly: true` and `format: uuid` as indicators
4. **Response Headers**: Extracts from `Location` and `X-Resource-Id` headers

### How It Works

1. **Extraction**: After each successful response (2xx), IDs are extracted and stored
2. **Storage**: IDs are indexed by resource type, parameter name, and endpoint
3. **Injection**: Before each request, stored IDs are injected into matching parameters
4. **Deletion Tracking**: DELETE requests mark IDs as deleted to avoid reuse

### Edge Cases Handled

- **Multiple IDs**: All ID-like fields are extracted from responses
- **Array Responses**: IDs extracted from all items in arrays
- **Nested IDs**: Deep extraction using JSONPath-like traversal
- **Type Matching**: Integer vs string vs UUID types are preserved
- **Resource Namespacing**: Same ID values for different resources are tracked separately

## Using Both Features Together

The HTML report includes ID extraction information when both features are enabled:

```bash
autotest run https://api.example.com/openapi.json \
  --extract-ids \
  --report-html=./reports/report.html
```

The report will show:
- Which IDs were extracted from which endpoints
- Which IDs were injected into which requests
- ID store state at end of test run

## Configuration Reference

### HTML Report Options

| Option | CLI Flag | Config Key | Default |
|--------|----------|------------|---------|
| Output path | `--report-html` | `reports.html.path` | None |
| Title | `--report-html-title` | `reports.html.title` | "API Test Report" |
| Include passed | `--report-include-passed` | `reports.html.include-passed-details` | false |
| Max body size | `--report-max-body-size` | `reports.html.max-body-size` | 10240 |

### ID Extraction Options

| Option | CLI Flag | Config Key | Default |
|--------|----------|------------|---------|
| Enable | `--extract-ids` | `id-extraction.enabled` | false |
| Strategy | `--id-injection-strategy` | `id-extraction.prefer` | "latest" |
| Verbose | `--id-verbose` | `id-extraction.verbose` | false |

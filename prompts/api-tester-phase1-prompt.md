# API Auto-Tester: Phase 1 Development Specification

## Project Overview

### Goal
Build an enhanced API testing tool by extending Schemathesis with two core features:
1. **HTML Report Generator** - Generate beautiful, interactive HTML reports with complete request/response data
2. **Smart ID Extraction** - Automatically extract and reuse resource IDs across dependent endpoints

### Approach
Clone the Schemathesis repository and build these features as extensions/plugins that integrate seamlessly with the existing codebase without breaking core functionality.

### Target Outcome
A tool that can:
- Run all existing Schemathesis tests
- Automatically extract IDs from responses and inject them into subsequent requests
- Generate a comprehensive HTML report showing all test results with full request/response details

---

## Prerequisites & Setup

### Repository Setup
1. Fork/clone Schemathesis from `https://github.com/schemathesis/schemathesis`
2. Create a new branch for your extensions (e.g., `feature/enhanced-testing`)
3. Set up a development environment with Python 3.9+
4. Install development dependencies

### Understanding Schemathesis Internals
Before building, familiarize yourself with these key Schemathesis components:
- `schemathesis/specs/openapi/` - OpenAPI schema parsing
- `schemathesis/runner/` - Test execution engine
- `schemathesis/models.py` - Core data models (Case, Response, etc.)
- `schemathesis/hooks.py` - Hook system for customization
- `schemathesis/cli/` - Command-line interface
- `schemathesis/transports/` - HTTP client handling

### Key Classes to Understand
- `Case` - Represents a single test case with all request data
- `Response` - Wraps HTTP response with validation methods
- `TestResult` - Stores results of test execution
- `APIOperation` - Represents a single API endpoint

---

## Feature 1: HTML Report Generator

### 1.1 What to Build

A report generation system that:
- Captures ALL request and response data during test execution
- Stores data in a structured format during the test run
- Generates a single, self-contained HTML file after tests complete
- Provides interactive features (collapsible sections, search, filtering)
- Works offline (no external CDN dependencies in final HTML)

### 1.2 Data to Capture

For each API call, capture the following:

#### Request Data
| Field | Description | Example |
|-------|-------------|---------|
| `timestamp` | When request was made | `2024-01-15T14:30:00.123Z` |
| `method` | HTTP method | `POST` |
| `url` | Full URL including query params | `https://api.example.com/users?active=true` |
| `path` | API path template | `/users/{id}` |
| `path_parameters` | Resolved path params | `{"id": "123"}` |
| `query_parameters` | Query string params | `{"active": "true"}` |
| `headers` | Request headers (sanitize auth) | `{"Content-Type": "application/json"}` |
| `body` | Request body (if any) | `{"name": "John", "email": "john@test.com"}` |
| `body_size` | Size in bytes | `45` |

#### Response Data
| Field | Description | Example |
|-------|-------------|---------|
| `status_code` | HTTP status code | `201` |
| `status_text` | Status description | `Created` |
| `headers` | Response headers | `{"Content-Type": "application/json"}` |
| `body` | Response body | `{"id": 123, "name": "John"}` |
| `body_size` | Size in bytes | `35` |
| `response_time_ms` | Time to receive response | `145` |

#### Test Metadata
| Field | Description | Example |
|-------|-------------|---------|
| `test_id` | Unique identifier | `uuid4()` |
| `operation_id` | OpenAPI operationId | `createUser` |
| `tags` | OpenAPI tags | `["users", "admin"]` |
| `test_phase` | Schemathesis phase | `fuzzing`, `examples`, `stateful` |
| `check_results` | Results of each check | `{"not_a_server_error": "pass"}` |
| `failure_reason` | If failed, why | `Schema validation failed` |
| `curl_command` | Reproducible curl | `curl -X POST ...` |

### 1.3 Report Structure

Design the HTML report with these sections:

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER                                                         │
│  - Test run timestamp                                           │
│  - API name/version (from OpenAPI info)                         │
│  - Base URL tested                                              │
│  - Total duration                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  EXECUTIVE SUMMARY                                              │
│  - Total tests: X                                               │
│  - Passed: Y (percentage)                                       │
│  - Failed: Z (percentage)                                       │
│  - Skipped: W                                                   │
│  - Pie chart or progress bar visualization                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ENDPOINTS OVERVIEW (Collapsible Table)                         │
│  ┌────────┬─────────────────┬────────┬────────┬───────────────┐ │
│  │ Method │ Path            │ Passed │ Failed │ Avg Time (ms) │ │
│  ├────────┼─────────────────┼────────┼────────┼───────────────┤ │
│  │ GET    │ /users          │ 10     │ 0      │ 45            │ │
│  │ POST   │ /users          │ 8      │ 2      │ 120           │ │
│  │ GET    │ /users/{id}     │ 15     │ 1      │ 35            │ │
│  └────────┴─────────────────┴────────┴────────┴───────────────┘ │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  FAILED TESTS (Expanded by default)                             │
│  Each failure shows:                                            │
│  - Endpoint + method                                            │
│  - Failure reason                                               │
│  - Request details (collapsible)                                │
│  - Response details (collapsible)                               │
│  - cURL command (copy button)                                   │
│  - Diff view if schema mismatch                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ALL TESTS (Searchable, Filterable, Paginated)                  │
│  - Filter by: status, method, endpoint, tag                     │
│  - Search by: URL, request body, response body                  │
│  - Sort by: time, status, endpoint                              │
│  - Each row expandable to show full details                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  FOOTER                                                         │
│  - Generation timestamp                                         │
│  - Tool version                                                 │
│  - Link to documentation                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.4 Implementation Approach

#### Step 1: Create Data Collector
Build a collector class that hooks into Schemathesis execution:

**Location:** Create new module `schemathesis/reporting/collector.py`

**Responsibilities:**
- Subscribe to test execution events
- Store test data in memory during run
- Handle large response bodies (truncation with full data option)
- Sanitize sensitive data (auth headers, tokens)

**Integration Points:**
- Hook into `after_call` hook to capture request/response
- Hook into check execution to capture validation results
- Integrate with the CLI runner to start/stop collection

#### Step 2: Create Data Models
Define Pydantic or dataclass models for structured data:

**Location:** Create `schemathesis/reporting/models.py`

**Models to Create:**
- `TestRunInfo` - Overall test run metadata
- `EndpointSummary` - Aggregated stats per endpoint
- `TestCaseResult` - Individual test case with all data
- `RequestData` - Structured request information
- `ResponseData` - Structured response information
- `CheckResult` - Individual check pass/fail

#### Step 3: Create Report Generator
Build the HTML generation engine:

**Location:** Create `schemathesis/reporting/html_generator.py`

**Approach:**
- Use Jinja2 templates for HTML structure
- Embed CSS inline for self-contained file
- Embed minimal JavaScript for interactivity
- Use data URIs for any icons/images
- Generate JSON data block for JavaScript consumption

**Template Structure:**
```
schemathesis/reporting/templates/
├── base.html           # Main template
├── components/
│   ├── header.html
│   ├── summary.html
│   ├── endpoints_table.html
│   ├── test_details.html
│   └── footer.html
├── styles/
│   └── report.css      # Embedded in final HTML
└── scripts/
    └── report.js       # Embedded in final HTML
```

#### Step 4: CLI Integration
Add new CLI options:

**New Flags:**
- `--report-html=<path>` - Generate HTML report at specified path
- `--report-html-title=<title>` - Custom report title
- `--report-include-passed` - Include passed test details (default: summary only)
- `--report-max-body-size=<bytes>` - Truncate bodies larger than this
- `--report-sanitize-headers=<list>` - Headers to redact

#### Step 5: Configuration Support
Add to `schemathesis.toml` configuration:

```toml
[report.html]
enabled = true
path = "./reports/api-test-report.html"
title = "API Test Report"
include_passed_details = false
max_body_size = 10240  # 10KB
sanitize_headers = ["Authorization", "X-API-Key"]
```

### 1.5 Recommended Third-Party Packages

| Package | Purpose | Why This Package |
|---------|---------|------------------|
| **Jinja2** | HTML templating | Already used by Schemathesis, powerful templating |
| **Pydantic** | Data validation/models | Type safety, serialization, already in project |
| **Pygments** | Syntax highlighting | Highlight JSON in request/response bodies |
| **humanize** | Human-readable formatting | "2 hours ago", "1.5 KB" formatting |
| **rich** | Console output | Progress bars, colored output during generation |

**For HTML/CSS (embedded, no runtime dependency):**
| Resource | Purpose |
|----------|---------|
| **Tailwind CSS (CDN or purged)** | Utility-first CSS framework |
| **Alpine.js** | Lightweight JS for interactivity |
| **Heroicons** | SVG icons (inline) |

### 1.6 Key Design Decisions

1. **Self-Contained HTML**
   - All CSS/JS must be embedded
   - No external dependencies for viewing
   - Report should work offline

2. **Performance for Large Test Runs**
   - Paginate results (don't render 10,000 tests at once)
   - Lazy-load test details on expand
   - Use virtual scrolling for very large datasets

3. **Body Truncation Strategy**
   - Truncate bodies > configurable limit in HTML view
   - Provide "Show Full" button that reveals complete data
   - Store full data in hidden elements or data attributes

4. **Sensitive Data Handling**
   - Redact Authorization headers by default
   - Configurable list of headers to sanitize
   - Option to completely exclude headers

### 1.7 Testing the Report Generator

**Unit Tests:**
- Test data collector captures all fields
- Test HTML generation with various data shapes
- Test truncation logic
- Test sanitization

**Integration Tests:**
- Run against sample API, verify report generated
- Verify report opens in browser
- Verify all interactive features work

**Visual Tests:**
- Test with 10, 100, 1000, 10000 test results
- Test with various response sizes
- Test with different content types (JSON, XML, binary)

---

## Feature 2: Smart ID Extraction

### 2.1 What to Build

An intelligent system that:
- Automatically detects ID fields in API responses
- Stores extracted IDs with context (which endpoint, which resource type)
- Injects stored IDs into subsequent requests that need them
- Handles multiple ID types (numeric, UUID, string)
- Supports nested ID extraction (e.g., `response.data.user.id`)
- Maintains ID relationships (user_id → created user's orders)

### 2.2 Problem This Solves

**Current Schemathesis Behavior:**
```
POST /users (body: {"name": "John"})        → 201, {"id": 123, "name": "John"}
GET  /users/{id} (id: randomly generated)  → 404 (ID doesn't exist!)
PUT  /users/{id} (id: randomly generated)  → 404 (ID doesn't exist!)
DELETE /users/{id} (id: randomly generated) → 404 (ID doesn't exist!)
```

**Desired Behavior:**
```
POST /users (body: {"name": "John"})        → 201, {"id": 123, "name": "John"}
                                               ↓ Extract ID: 123
GET  /users/{id} (id: 123)                  → 200, {"id": 123, "name": "John"} ✓
PUT  /users/{id} (id: 123)                  → 200 ✓
DELETE /users/{id} (id: 123)                → 204 ✓
```

### 2.3 ID Detection Strategies

Implement multiple strategies to detect IDs:

#### Strategy 1: Path Parameter Matching
Match response fields to path parameters in other endpoints:

```yaml
# If endpoint exists: GET /users/{userId}
# And POST /users returns: {"userId": 123, ...}
# Then extract "userId" from response
```

**Logic:**
1. Parse all endpoints, collect path parameters
2. When a response comes in, check if any field name matches a path parameter
3. If match found, store the value

#### Strategy 2: Common ID Field Names
Look for conventional ID field names:

```python
ID_FIELD_PATTERNS = [
    "id",
    "*_id",      # user_id, order_id
    "*Id",       # userId, orderId
    "uuid",
    "*_uuid",
    "*Uuid",
    "identifier",
    "key",
    "pk",        # primary key
]
```

#### Strategy 3: OpenAPI Schema Hints
Use schema information to identify IDs:

```yaml
# In OpenAPI schema
components:
  schemas:
    User:
      properties:
        id:
          type: integer
          format: int64
          readOnly: true  # ← Hint: this is auto-generated, likely an ID
```

**Indicators:**
- `readOnly: true` often indicates auto-generated IDs
- `format: uuid` indicates UUID type
- Field in response but not in request body → likely auto-generated

#### Strategy 4: Response Header Extraction
Some APIs return IDs in headers:

```
POST /users
Response Headers:
  Location: /users/123        ← Extract 123
  X-Resource-Id: 123          ← Extract 123
```

#### Strategy 5: Link Relation Analysis (OpenAPI Links)
Use OpenAPI 3.x links for explicit relationships:

```yaml
paths:
  /users:
    post:
      responses:
        201:
          links:
            GetUser:
              operationId: getUser
              parameters:
                userId: '$response.body#/id'  # ← Explicit extraction path
```

### 2.4 ID Storage Design

#### Storage Structure
Design an ID store that maintains:

```
IDStore:
├── by_resource_type:
│   ├── "User": [123, 456, 789]
│   ├── "Order": ["ord-001", "ord-002"]
│   └── "Product": [...]
│
├── by_path_parameter:
│   ├── "userId": [123, 456, 789]
│   ├── "orderId": ["ord-001", "ord-002"]
│   └── "productId": [...]
│
├── by_endpoint:
│   ├── "POST /users": [
│   │     {id: 123, extracted_at: timestamp, full_response: {...}},
│   │     {id: 456, extracted_at: timestamp, full_response: {...}}
│   │   ]
│   └── ...
│
└── relationships:
    └── "User:123": {
          "orders": ["ord-001", "ord-002"],
          "profile": "prof-123"
        }
```

#### Storage Interface
```
IDStore Interface:
├── store(resource_type, id_field, value, context)
├── get_random(resource_type) → value
├── get_latest(resource_type) → value
├── get_all(resource_type) → [values]
├── get_for_parameter(param_name) → value
├── clear(resource_type=None)  # None = clear all
└── get_related(resource_type, id, relation) → [values]
```

### 2.5 ID Injection Logic

#### When to Inject
Inject IDs into:
1. **Path Parameters**: `/users/{userId}` → `/users/123`
2. **Query Parameters**: `/orders?userId=X` → `/orders?userId=123`
3. **Request Body**: `{"userId": X}` → `{"userId": 123}`
4. **Headers**: `X-User-Id: X` → `X-User-Id: 123`

#### Injection Priority
When multiple IDs are available, prioritize:

1. **Most Recent**: IDs from the most recent response (likely still valid)
2. **Same Test Sequence**: IDs created in the same stateful test sequence
3. **Type Match**: Prefer IDs that match expected type (int vs string vs UUID)
4. **Random from Pool**: Fall back to random selection from stored IDs

#### Injection Decision Flow

```
For each parameter needing a value:
│
├─→ Is it a path parameter?
│   ├─→ Do we have stored IDs for this param name?
│   │   └─→ YES: Use stored ID (latest or random based on config)
│   │   └─→ NO: Check by inferred resource type
│   │       └─→ Found: Use it
│   │       └─→ Not Found: Let Schemathesis generate random value
│
├─→ Is it a body field with ID-like name?
│   └─→ Same logic as above
│
└─→ Is it a query parameter referencing a resource?
    └─→ Same logic as above
```

### 2.6 Configuration Options

Allow users to configure ID extraction behavior:

```yaml
# schemathesis.toml or custom config
[id_extraction]
enabled = true

# Detection strategies to use
strategies = [
  "path_parameter_matching",
  "common_id_fields", 
  "schema_hints",
  "response_headers",
  "openapi_links"
]

# Custom ID field patterns (in addition to defaults)
custom_id_patterns = [
  "resourceId",
  "*_ref",
  "external_id"
]

# Explicit mappings (override auto-detection)
[id_extraction.mappings]
"POST /users" = { extract = "id", inject_to = ["userId", "user_id"] }
"POST /orders" = { extract = "orderId", inject_to = ["orderId", "order_id"] }

# Fields to never treat as IDs
ignore_fields = ["created_at", "updated_at", "version"]

# Injection behavior
[id_extraction.injection]
prefer = "latest"  # "latest", "random", "first"
fallback_to_generated = true  # If no stored ID, use Schemathesis generation
```

### 2.7 Implementation Approach

#### Step 1: Create ID Extractor Module
**Location:** Create `schemathesis/extraction/id_extractor.py`

**Responsibilities:**
- Parse response bodies for ID-like fields
- Match against known patterns
- Handle nested structures (JSONPath or similar)
- Return extracted IDs with metadata

**Key Functions:**
- `detect_id_fields(response_body, schema=None) → List[ExtractedID]`
- `match_to_parameters(extracted_ids, all_endpoints) → Dict[param_name, id_value]`
- `extract_from_headers(response_headers) → List[ExtractedID]`

#### Step 2: Create ID Store
**Location:** Create `schemathesis/extraction/id_store.py`

**Responsibilities:**
- Thread-safe storage (tests may run in parallel)
- Efficient lookup by multiple keys
- TTL support (IDs might become invalid over time)
- Persistence option (save/load between runs)

**Implementation Notes:**
- Use threading locks for thread safety
- Consider using a simple SQLite for persistence
- Implement LRU eviction if store gets too large

#### Step 3: Create ID Injector
**Location:** Create `schemathesis/extraction/id_injector.py`

**Responsibilities:**
- Hook into test case generation
- Modify Case objects before request is made
- Replace placeholder values with stored IDs
- Log injection decisions for debugging

**Integration Point:**
- Use `before_call` hook or modify `Case` generation in `generation/` module

#### Step 4: Create Resource Type Inferrer
**Location:** Create `schemathesis/extraction/resource_inferrer.py`

**Responsibilities:**
- Infer resource type from endpoint path
- Handle plural/singular (users → User, /user/{id} → User)
- Map path parameters to resource types
- Handle nested resources (/users/{userId}/orders → Order under User)

**Logic:**
```
/users         → resource_type: "User"
/users/{id}    → resource_type: "User"  
/users/{userId}/orders → resource_type: "Order", parent: "User"
/api/v1/customers/{customerId} → resource_type: "Customer"
```

#### Step 5: Integration with Schemathesis Hooks
Create hooks that tie everything together:

**Hook: `after_call`**
- Extract IDs from successful responses (2xx)
- Store extracted IDs in ID store
- Associate IDs with resource types and parameters

**Hook: `before_generate_body` (may need custom hook)**
- Check if body has ID-like fields
- Inject stored IDs where appropriate

**Hook: `before_generate_path_parameters`**
- Look up stored IDs for path parameters
- Replace generated values with stored IDs

#### Step 6: CLI Integration
Add new CLI options:

**New Flags:**
- `--extract-ids` / `--no-extract-ids` - Enable/disable ID extraction
- `--id-injection-strategy=<strategy>` - latest|random|first
- `--id-store-persist=<path>` - Persist ID store to file
- `--id-verbose` - Log all extraction/injection decisions

#### Step 7: Debug/Reporting Integration
Add ID extraction info to reports:

- Which IDs were extracted from which endpoint
- Which IDs were injected into which requests
- ID store state at end of test run
- Warnings for unmatched parameters

### 2.8 Recommended Third-Party Packages

| Package | Purpose | Why This Package |
|---------|---------|------------------|
| **jsonpath-ng** | JSONPath queries | Extract nested IDs with paths like `$.data.user.id` |
| **inflect** | Pluralization | Convert "users" → "User", "people" → "Person" |
| **parse** | String parsing | Extract IDs from Location headers |
| **cachetools** | Caching utilities | LRU cache, TTL cache for ID store |

### 2.9 Edge Cases to Handle

1. **Multiple IDs in Response**
   ```json
   {"id": 123, "userId": 456, "createdBy": 789}
   ```
   → Store all with appropriate context

2. **Array Responses**
   ```json
   [{"id": 1}, {"id": 2}, {"id": 3}]
   ```
   → Extract all IDs from array

3. **Nested IDs**
   ```json
   {"data": {"user": {"id": 123}}}
   ```
   → Use JSONPath to extract

4. **Different ID Types**
   ```json
   {"id": 123}           // integer
   {"id": "abc-123"}     // string
   {"id": "550e8400-..."}// UUID
   ```
   → Preserve types, match to parameter types

5. **ID Reuse Across Resources**
   ```
   POST /users → {"id": 1}
   POST /products → {"id": 1}  // Same ID, different resource!
   ```
   → Namespace by resource type

6. **ID Invalidation**
   ```
   POST /users → {"id": 123}
   DELETE /users/123 → 204
   GET /users/123 → Should NOT use 123 anymore
   ```
   → Mark IDs as deleted, remove from pool

### 2.10 Testing the ID Extraction System

**Unit Tests:**
- Test each detection strategy independently
- Test ID store CRUD operations
- Test injection logic with various scenarios
- Test resource type inference

**Integration Tests:**
- Test with real OpenAPI specs
- Test full flow: extract → store → inject
- Test with stateful sequences
- Test thread safety with parallel execution

**Test APIs to Use:**
- JSONPlaceholder (simple CRUD)
- PetStore (OpenAPI example)
- Custom mock API with edge cases

---

## Integration Architecture

### How Both Features Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Execution Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Load OpenAPI Schema                                         │
│     └─→ Parse endpoints, identify path parameters               │
│     └─→ Initialize ID Store with expected parameter names       │
│                                                                 │
│  2. Generate Test Case                                          │
│     └─→ [ID Injector] Check if path params have stored IDs      │
│     └─→ [ID Injector] Inject stored IDs or use generated        │
│                                                                 │
│  3. Execute Request                                             │
│     └─→ [Data Collector] Capture full request data              │
│     └─→ Send HTTP request                                       │
│     └─→ [Data Collector] Capture full response data             │
│                                                                 │
│  4. Process Response                                            │
│     └─→ [ID Extractor] If 2xx, extract IDs from response        │
│     └─→ [ID Store] Store extracted IDs with context             │
│     └─→ [Data Collector] Record extraction metadata             │
│     └─→ Run Schemathesis checks                                 │
│     └─→ [Data Collector] Record check results                   │
│                                                                 │
│  5. After All Tests                                             │
│     └─→ [Report Generator] Generate HTML report                 │
│     └─→ Include ID extraction/injection summary                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Shared Components

Both features share:
- **Configuration System**: Unified config in `schemathesis.toml`
- **Logging**: Consistent logging format
- **CLI Integration**: Related flags grouped together

---

## Development Roadmap

### Week 1-2: Foundation & Data Collection

**Milestone 1: Data Collection Infrastructure**
- [ ] Create `schemathesis/reporting/` module structure
- [ ] Define Pydantic models for test data
- [ ] Implement DataCollector class
- [ ] Hook into Schemathesis execution
- [ ] Write unit tests for collector
- [ ] Verify data capture with sample API

**Deliverable:** Running tests populates data structures with complete request/response info

### Week 3-4: HTML Report Generator

**Milestone 2: Basic HTML Report**
- [ ] Set up Jinja2 templates structure
- [ ] Create base HTML template with CSS
- [ ] Implement summary section
- [ ] Implement endpoints table
- [ ] Implement failed tests section
- [ ] Add CLI flag `--report-html`
- [ ] Write integration tests

**Deliverable:** Basic HTML report generates after test run

**Milestone 3: Enhanced HTML Report**
- [ ] Add interactivity (collapsible sections)
- [ ] Add search/filter functionality
- [ ] Add syntax highlighting for JSON
- [ ] Add copy-to-clipboard for cURL
- [ ] Optimize for large test runs
- [ ] Add configuration options
- [ ] Write visual tests

**Deliverable:** Full-featured interactive HTML report

### Week 5-6: ID Extraction System

**Milestone 4: ID Detection & Storage**
- [ ] Create `schemathesis/extraction/` module structure
- [ ] Implement ID detection strategies
- [ ] Create thread-safe ID Store
- [ ] Implement resource type inference
- [ ] Write unit tests for each component

**Deliverable:** System can detect and store IDs from responses

**Milestone 5: ID Injection**
- [ ] Implement ID Injector
- [ ] Hook into test case generation
- [ ] Add configuration options
- [ ] Add CLI flags
- [ ] Write integration tests

**Deliverable:** IDs automatically flow from POST to GET/PUT/DELETE

### Week 7: Integration & Polish

**Milestone 6: Full Integration**
- [ ] Integrate ID info into HTML report
- [ ] Add ID extraction summary section
- [ ] Test both features together
- [ ] Performance testing
- [ ] Documentation

**Deliverable:** Both features working together seamlessly

### Week 8: Testing & Release Prep

**Milestone 7: Quality Assurance**
- [ ] Full test suite passes
- [ ] Test against multiple real-world APIs
- [ ] Performance benchmarks
- [ ] Documentation complete
- [ ] Example configurations

**Deliverable:** Production-ready Phase 1

---

## File Structure (Proposed)

```
schemathesis/
├── extraction/                    # NEW: ID Extraction Module
│   ├── __init__.py
│   ├── id_extractor.py           # ID detection logic
│   ├── id_store.py               # ID storage
│   ├── id_injector.py            # ID injection into requests
│   ├── resource_inferrer.py      # Resource type inference
│   ├── strategies/               # Detection strategies
│   │   ├── __init__.py
│   │   ├── path_parameter.py
│   │   ├── common_fields.py
│   │   ├── schema_hints.py
│   │   ├── response_headers.py
│   │   └── openapi_links.py
│   └── tests/
│       ├── test_extractor.py
│       ├── test_store.py
│       └── test_injector.py
│
├── reporting/                     # NEW: Reporting Module
│   ├── __init__.py
│   ├── collector.py              # Data collection during tests
│   ├── models.py                 # Data models
│   ├── html_generator.py         # HTML report generation
│   ├── templates/                # Jinja2 templates
│   │   ├── base.html
│   │   ├── components/
│   │   │   ├── header.html
│   │   │   ├── summary.html
│   │   │   ├── endpoints_table.html
│   │   │   ├── failed_tests.html
│   │   │   ├── all_tests.html
│   │   │   └── footer.html
│   │   └── partials/
│   │       ├── request_details.html
│   │       └── response_details.html
│   ├── static/                   # To be embedded
│   │   ├── styles.css
│   │   └── scripts.js
│   └── tests/
│       ├── test_collector.py
│       ├── test_models.py
│       └── test_html_generator.py
│
├── cli/
│   ├── ... (existing files)
│   └── options.py                # MODIFY: Add new CLI options
│
├── configuration/                 # MODIFY: Add new config sections
│   └── ...
│
└── hooks.py                      # MODIFY: Register new hooks
```

---

## Success Criteria

### HTML Report Generator
- [ ] Generates self-contained HTML file
- [ ] Displays all test results with request/response data
- [ ] Interactive features work (search, filter, collapse)
- [ ] Handles 10,000+ tests without performance issues
- [ ] Works offline (no external dependencies)
- [ ] Sensitive data properly sanitized

### Smart ID Extraction
- [ ] Correctly identifies ID fields in >90% of standard APIs
- [ ] Stores and retrieves IDs efficiently
- [ ] Injects IDs into path, query, and body parameters
- [ ] Handles edge cases (arrays, nested, multiple IDs)
- [ ] Thread-safe for parallel execution
- [ ] Configurable behavior via CLI and config file

### Integration
- [ ] Both features work together seamlessly
- [ ] No regression in existing Schemathesis functionality
- [ ] Clear documentation and examples
- [ ] Comprehensive test coverage

---

## Appendix: Useful References

### Schemathesis Documentation
- Main docs: https://schemathesis.readthedocs.io/
- Hooks reference: https://schemathesis.readthedocs.io/en/latest/reference/hooks/
- Configuration: https://schemathesis.github.io/schemathesis/configuration/

### Related Projects
- hypothesis-jsonschema: https://github.com/Zac-HD/hypothesis-jsonschema
- jsonpath-ng: https://github.com/h2non/jsonpath-ng
- Jinja2: https://jinja.palletsprojects.com/

### OpenAPI Specification
- OpenAPI 3.1: https://spec.openapis.org/oas/v3.1.0
- OpenAPI Links: https://spec.openapis.org/oas/v3.1.0#link-object

---

*This specification document serves as the blueprint for Phase 1 development. Adjust timelines and scope based on available resources and priorities.*

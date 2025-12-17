# API Auto-Tester: Phase 2 Development Specification

## Project Overview

### Goal
Extend the API Auto-Tester tool (built on autotest) with two powerful features:
1. **Workflow Definitions** - Define and execute CRUD sequences and complex multi-step API test scenarios
2. **YAML Config System** - Unified, hierarchical configuration system for all tool settings

### Prerequisites
This phase builds upon Phase 1 features:
- ✅ HTML Report Generator (from Phase 1)
- ✅ Smart ID Extraction (from Phase 1)

### Target Outcome
A tool that can:
- Execute predefined test workflows (e.g., Create → Read → Update → Delete)
- Support complex multi-step scenarios with conditional logic
- Manage all configuration through a single, well-structured YAML file
- Support environment-specific overrides
- Provide inheritance and reusability in configurations

---

## Feature 1: Workflow Definitions (CRUD Sequence Testing)

### 1.1 What to Build

A workflow engine that:
- Defines test sequences as declarative YAML workflows
- Executes steps in order with dependency management
- Passes data between steps (extracted IDs, response fields)
- Supports conditional execution (if previous step succeeded/failed)
- Handles setup and teardown (cleanup created resources)
- Integrates with existing autotest test generation
- Reports workflow-level results (not just individual requests)

### 1.2 Problem This Solves

**Current State (Even with Phase 1 ID Extraction):**
- Tests run in unpredictable order
- No guarantee that POST runs before GET
- Can't test business logic sequences
- No way to verify data consistency across operations
- Can't test complex scenarios like "create user → create order for user → cancel order"

**Desired State:**
- Define explicit test sequences
- Guarantee execution order
- Verify data flows correctly between operations
- Test real-world usage patterns
- Automatic cleanup of test data

### 1.3 Workflow Definition Structure

#### Basic Workflow Schema

```yaml
workflows:
  - name: "user_crud_workflow"
    description: "Test complete user lifecycle"
    tags: ["users", "crud", "critical"]
    
    # Variables available throughout workflow
    variables:
      base_email: "test-${timestamp}@example.com"
      
    # Setup steps (run before main steps)
    setup:
      - name: "ensure_clean_state"
        action: "cleanup_users_by_email"
        params:
          email_pattern: "test-*@example.com"
    
    # Main workflow steps
    steps:
      - name: "create_user"
        endpoint: "POST /users"
        request:
          body:
            name: "Test User"
            email: "${base_email}"
            role: "member"
        expect:
          status: [201]
          body:
            id: "${extract:user_id}"  # Extract and store
            name: "Test User"
        on_failure: "abort"  # abort | continue | retry
        
      - name: "verify_user_created"
        endpoint: "GET /users/${user_id}"
        depends_on: ["create_user"]
        expect:
          status: [200]
          body:
            id: "${user_id}"
            name: "Test User"
            email: "${base_email}"
            
      - name: "update_user"
        endpoint: "PUT /users/${user_id}"
        depends_on: ["verify_user_created"]
        request:
          body:
            name: "Updated User"
        expect:
          status: [200]
          body:
            name: "Updated User"
            
      - name: "delete_user"
        endpoint: "DELETE /users/${user_id}"
        depends_on: ["update_user"]
        expect:
          status: [204]
        
      - name: "verify_user_deleted"
        endpoint: "GET /users/${user_id}"
        depends_on: ["delete_user"]
        expect:
          status: [404]
    
    # Teardown steps (always run, even on failure)
    teardown:
      - name: "cleanup_user"
        endpoint: "DELETE /users/${user_id}"
        condition: "${user_id} != null"
        ignore_failure: true
```

#### Advanced Workflow Features

```yaml
workflows:
  - name: "order_processing_workflow"
    description: "Test complete order lifecycle with multiple entities"
    
    # Workflow-level settings
    settings:
      timeout: 300  # seconds for entire workflow
      retry_failed_steps: 2
      parallel_steps: false  # Run steps sequentially
      
    variables:
      timestamp: "${now:format=YYYYMMDDHHmmss}"
      random_suffix: "${random:length=8}"
      
    steps:
      # Step with data generation
      - name: "create_customer"
        endpoint: "POST /customers"
        request:
          body:
            name: "${faker:name}"
            email: "${faker:email}"
            phone: "${faker:phone}"
        extract:
          customer_id: "$.id"
          customer_email: "$.email"
          
      # Step with loop (create multiple items)
      - name: "create_products"
        endpoint: "POST /products"
        loop:
          count: 3
          as: "product_index"
        request:
          body:
            name: "Product ${product_index}"
            price: "${random:min=10,max=100}"
        extract:
          product_ids: "$.id"  # Collects into array
          
      # Step with conditional execution
      - name: "apply_discount"
        endpoint: "POST /discounts"
        condition: "${len(product_ids)} >= 3"
        request:
          body:
            code: "BULK_${random_suffix}"
            percentage: 10
        extract:
          discount_id: "$.id"
          
      # Step using data from previous steps
      - name: "create_order"
        endpoint: "POST /orders"
        depends_on: ["create_customer", "create_products"]
        request:
          body:
            customer_id: "${customer_id}"
            items: "${map(product_ids, id => {product_id: id, quantity: 1})}"
            discount_code: "${discount_id ?? null}"
        expect:
          status: [201]
          body:
            status: "pending"
        extract:
          order_id: "$.id"
          order_total: "$.total"
          
      # Polling step (wait for async operation)
      - name: "wait_for_order_processing"
        endpoint: "GET /orders/${order_id}"
        poll:
          interval: 2  # seconds
          timeout: 30  # seconds
          until:
            body:
              status: ["processing", "completed"]
              
      # Step with custom validation
      - name: "verify_order_total"
        endpoint: "GET /orders/${order_id}"
        expect:
          status: [200]
          custom:
            - "response.body.total > 0"
            - "response.body.items.length == 3"
            - "response.body.customer_id == ${customer_id}"
            
      # Negative test step
      - name: "verify_duplicate_order_rejected"
        endpoint: "POST /orders"
        request:
          body:
            customer_id: "${customer_id}"
            items: "${map(product_ids, id => {product_id: id, quantity: 1})}"
        expect:
          status: [400, 409]
          body:
            error: "${contains:'duplicate'}"
```

### 1.4 Workflow Components Deep Dive

#### 1.4.1 Step Definition

Each step in a workflow can have:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Unique identifier for the step |
| `endpoint` | string | ✅ | HTTP method + path (e.g., "POST /users") |
| `description` | string | ❌ | Human-readable description |
| `depends_on` | array | ❌ | List of step names that must complete first |
| `condition` | string | ❌ | Expression that must be true to execute |
| `request` | object | ❌ | Request configuration |
| `expect` | object | ❌ | Expected response validation |
| `extract` | object | ❌ | Data to extract from response |
| `on_failure` | string | ❌ | Action on failure: abort/continue/retry |
| `retry` | object | ❌ | Retry configuration |
| `timeout` | number | ❌ | Step-specific timeout in seconds |
| `loop` | object | ❌ | Loop configuration for repeated execution |
| `poll` | object | ❌ | Polling configuration for async operations |

#### 1.4.2 Request Configuration

```yaml
request:
  # Headers (merged with global headers)
  headers:
    X-Custom-Header: "value"
    X-Request-ID: "${uuid}"
    
  # Query parameters
  query:
    page: 1
    limit: 10
    filter: "active"
    
  # Path parameters (usually auto-resolved from endpoint)
  path:
    userId: "${user_id}"
    
  # Request body
  body:
    name: "Test"
    nested:
      field: "value"
      
  # Form data (alternative to body)
  form:
    file: "${file:path=/tmp/test.pdf}"
    description: "Test file"
    
  # Body from file
  body_file: "./fixtures/large_payload.json"
  
  # Override content type
  content_type: "application/xml"
```

#### 1.4.3 Expectation Configuration

```yaml
expect:
  # Status code(s)
  status: [200, 201]  # Any of these
  
  # Response headers
  headers:
    Content-Type: "application/json"
    X-Request-ID: "${request.headers.X-Request-ID}"  # Must match request
    
  # Response body validation
  body:
    # Exact match
    id: 123
    
    # Type checking
    name: "${type:string}"
    age: "${type:number}"
    active: "${type:boolean}"
    tags: "${type:array}"
    
    # Pattern matching
    email: "${regex:^[a-z]+@[a-z]+\\.[a-z]+$}"
    uuid: "${regex:^[0-9a-f]{8}-[0-9a-f]{4}-}"
    
    # Comparison operators
    count: "${gte:10}"      # Greater than or equal
    price: "${between:0,100}"
    
    # Contains check
    roles: "${contains:admin}"
    
    # Array validation
    items:
      "${length}": "${gte:1}"
      "${each}":
        id: "${type:number}"
        name: "${type:string}"
        
    # Nested extraction
    data:
      user:
        id: "${extract:nested_user_id}"
        
  # Response time constraint
  response_time_ms: "${lte:500}"
  
  # Schema validation (use OpenAPI schema)
  schema: true  # Validate against OpenAPI response schema
  
  # Custom expressions
  custom:
    - "response.body.total == response.body.items.reduce((sum, i) => sum + i.price, 0)"
    - "response.body.created_at <= now()"
```

#### 1.4.4 Variable System

Variables can be defined and used throughout workflows:

```yaml
# Global variables (available in all workflows)
variables:
  api_version: "v1"
  default_timeout: 30
  
workflows:
  - name: "my_workflow"
    # Workflow-level variables
    variables:
      timestamp: "${now:format=YYYYMMDDHHmmss}"
      
    steps:
      - name: "step1"
        # Step-level variables
        variables:
          step_var: "local_value"
```

**Variable Sources:**

| Syntax | Description | Example |
|--------|-------------|---------|
| `${var_name}` | Reference a variable | `${user_id}` |
| `${now}` | Current timestamp | `2024-01-15T14:30:00Z` |
| `${now:format=...}` | Formatted timestamp | `${now:format=YYYYMMDD}` |
| `${uuid}` | Generate UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `${random}` | Random string | `a8f3b2c1` |
| `${random:length=N}` | Random string of length N | `${random:length=16}` |
| `${random:min=X,max=Y}` | Random number in range | `${random:min=1,max=100}` |
| `${faker:type}` | Faker-generated data | `${faker:email}` |
| `${env:VAR_NAME}` | Environment variable | `${env:API_KEY}` |
| `${file:path=...}` | File contents | `${file:path=./data.json}` |
| `${extract:name}` | Mark for extraction | `${extract:user_id}` |
| `${response.field}` | Previous response data | `${response.body.id}` |
| `${steps.name.field}` | Specific step's data | `${steps.create_user.response.body.id}` |

#### 1.4.5 Data Extraction

Extract data from responses for use in subsequent steps:

```yaml
steps:
  - name: "create_user"
    endpoint: "POST /users"
    extract:
      # Simple extraction (JSONPath)
      user_id: "$.id"
      user_email: "$.email"
      
      # Nested extraction
      profile_id: "$.profile.id"
      
      # Array extraction (gets all matching values)
      tag_ids: "$.tags[*].id"
      
      # First item from array
      first_role: "$.roles[0]"
      
      # Filtered extraction
      admin_role: "$.roles[?(@.name=='admin')].id"
      
      # Header extraction
      request_id: "$headers.X-Request-ID"
      
      # Full response storage
      full_response: "$"
      
  - name: "use_extracted"
    endpoint: "GET /users/${user_id}/profile/${profile_id}"
    # Variables are automatically available
```

#### 1.4.6 Conditional Execution

```yaml
steps:
  - name: "check_feature_flag"
    endpoint: "GET /features/premium"
    extract:
      premium_enabled: "$.enabled"
      
  - name: "create_premium_user"
    endpoint: "POST /users/premium"
    condition: "${premium_enabled} == true"
    
  - name: "create_basic_user"
    endpoint: "POST /users/basic"
    condition: "${premium_enabled} == false"
    
  - name: "conditional_with_expression"
    endpoint: "POST /batch"
    condition: "${len(items)} > 0 && ${user_type} == 'admin'"
```

#### 1.4.7 Loops

```yaml
steps:
  # Fixed count loop
  - name: "create_multiple_users"
    endpoint: "POST /users"
    loop:
      count: 5
      as: "index"  # Available as ${index} (0-4)
    request:
      body:
        name: "User ${index + 1}"
        email: "user${index + 1}@test.com"
    extract:
      user_ids: "$.id"  # Collects all IDs into array
      
  # Loop over array
  - name: "delete_users"
    endpoint: "DELETE /users/${current_user_id}"
    loop:
      over: "${user_ids}"
      as: "current_user_id"
      
  # Loop with condition
  - name: "retry_failed"
    endpoint: "POST /process"
    loop:
      count: 3
      as: "attempt"
      until: "${response.status} == 200"
      delay: 2  # seconds between iterations
```

#### 1.4.8 Polling (Async Operations)

```yaml
steps:
  - name: "start_job"
    endpoint: "POST /jobs"
    extract:
      job_id: "$.id"
      
  - name: "wait_for_job"
    endpoint: "GET /jobs/${job_id}"
    poll:
      interval: 5       # Check every 5 seconds
      timeout: 120      # Give up after 2 minutes
      initial_delay: 2  # Wait before first poll
      until:
        # Success conditions (any of these)
        body:
          status: ["completed", "finished"]
      while:
        # Continue polling while these are true
        body:
          status: ["pending", "processing"]
      on_timeout: "fail"  # fail | continue
```

### 1.5 Implementation Approach

#### Step 1: Workflow Parser
**Location:** Create `autotest/workflows/parser.py`

**Responsibilities:**
- Parse YAML workflow definitions
- Validate workflow structure against schema
- Resolve variable references
- Build execution graph from dependencies

**Key Components:**
- `WorkflowParser` - Main parser class
- `StepParser` - Parse individual steps
- `VariableResolver` - Resolve ${...} expressions
- `DependencyResolver` - Build execution order

#### Step 2: Workflow Models
**Location:** Create `autotest/workflows/models.py`

**Models to Create:**

```
Workflow
├── name: str
├── description: Optional[str]
├── tags: List[str]
├── variables: Dict[str, Any]
├── settings: WorkflowSettings
├── setup: List[WorkflowStep]
├── steps: List[WorkflowStep]
├── teardown: List[WorkflowStep]

WorkflowStep
├── name: str
├── endpoint: EndpointReference
├── request: RequestConfig
├── expect: ExpectConfig
├── extract: Dict[str, str]
├── depends_on: List[str]
├── condition: Optional[str]
├── loop: Optional[LoopConfig]
├── poll: Optional[PollConfig]
├── on_failure: FailureAction

RequestConfig
├── headers: Dict[str, str]
├── query: Dict[str, Any]
├── path: Dict[str, Any]
├── body: Any
├── body_file: Optional[str]
├── content_type: Optional[str]

ExpectConfig
├── status: List[int]
├── headers: Dict[str, Any]
├── body: Dict[str, Any]
├── response_time_ms: Optional[int]
├── schema: bool
├── custom: List[str]

LoopConfig
├── count: Optional[int]
├── over: Optional[str]
├── as_var: str
├── until: Optional[str]
├── delay: Optional[float]

PollConfig
├── interval: float
├── timeout: float
├── initial_delay: float
├── until: Dict[str, Any]
├── while_condition: Dict[str, Any]
├── on_timeout: str
```

#### Step 3: Expression Engine
**Location:** Create `autotest/workflows/expressions.py`

**Responsibilities:**
- Parse and evaluate ${...} expressions
- Support built-in functions (now, uuid, random, etc.)
- Support Faker integration
- Support JSONPath for extraction
- Type coercion and validation

**Expression Types to Support:**

| Category | Functions |
|----------|-----------|
| **Time** | `now`, `now:format=`, `timestamp` |
| **Random** | `uuid`, `random`, `random:length=`, `random:min=,max=` |
| **Faker** | `faker:name`, `faker:email`, `faker:phone`, etc. |
| **Data** | `file:path=`, `env:VAR_NAME` |
| **Logic** | `if(cond, true_val, false_val)` |
| **Array** | `len()`, `first()`, `last()`, `map()`, `filter()` |
| **String** | `upper()`, `lower()`, `trim()`, `contains()` |
| **Comparison** | `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `between` |
| **Type** | `type:string`, `type:number`, `type:boolean`, `type:array` |
| **Pattern** | `regex:pattern`, `matches()` |

#### Step 4: Workflow Executor
**Location:** Create `autotest/workflows/executor.py`

**Responsibilities:**
- Execute workflows step by step
- Manage variable context
- Handle dependencies and ordering
- Execute loops and polling
- Manage timeouts
- Handle failures according to configuration
- Integrate with autotest HTTP client

**Execution Flow:**

```
WorkflowExecutor.run(workflow):
│
├─→ Initialize variable context
├─→ Run setup steps
│   └─→ For each setup step: execute_step()
│
├─→ Build execution order from dependencies
├─→ Run main steps in order
│   └─→ For each step:
│       ├─→ Check condition
│       ├─→ Resolve variables in request
│       ├─→ Execute HTTP request (or loop/poll)
│       ├─→ Validate response against expectations
│       ├─→ Extract data into context
│       ├─→ Handle failure if needed
│       └─→ Record result
│
├─→ Run teardown steps (always)
│   └─→ For each teardown step: execute_step()
│
└─→ Return WorkflowResult
```

#### Step 5: Dependency Graph Builder
**Location:** Create `autotest/workflows/dependency_graph.py`

**Responsibilities:**
- Parse `depends_on` relationships
- Detect circular dependencies
- Build topological sort order
- Handle parallel execution (if enabled)

**Algorithm:**
1. Build adjacency list from depends_on
2. Detect cycles using DFS
3. Topological sort for execution order
4. Group independent steps for parallel execution

#### Step 6: Response Validator
**Location:** Create `autotest/workflows/validator.py`

**Responsibilities:**
- Validate responses against expectations
- Support all comparison operators
- Handle custom expressions
- Integrate with autotest schema validation
- Generate detailed failure messages

#### Step 7: Workflow Reporter Integration
**Location:** Extend `autotest/reporting/` from Phase 1

**Additions:**
- Workflow-level summary in HTML report
- Step execution timeline visualization
- Data flow visualization (what was extracted/used)
- Workflow success/failure at workflow level

#### Step 8: CLI Integration
**New Commands:**

```bash
# Run specific workflow
autotest workflow run ./workflows/user_crud.yaml

# Run all workflows in directory
autotest workflow run ./workflows/

# Run workflows by tag
autotest workflow run ./workflows/ --tags critical,smoke

# List available workflows
autotest workflow list ./workflows/

# Validate workflow syntax
autotest workflow validate ./workflows/user_crud.yaml

# Generate workflow from OpenAPI (auto-detect CRUD)
autotest workflow generate --from-spec ./openapi.yaml --output ./workflows/
```

### 1.6 Recommended Third-Party Packages

| Package | Purpose | Why This Package |
|---------|---------|------------------|
| **PyYAML** | YAML parsing | Standard YAML parser, already in project |
| **jsonpath-ng** | JSONPath extraction | Powerful JSONPath implementation |
| **Faker** | Test data generation | Industry standard for fake data |
| **Jinja2** | Template rendering | For variable substitution (already in project) |
| **pydantic** | Data validation | Model validation, already in project |
| **networkx** | Dependency graph | Graph algorithms for dependency resolution |
| **simpleeval** | Safe expression evaluation | Evaluate custom expressions safely |
| **croniter** | (Optional) Scheduling | If adding scheduled workflow runs |

### 1.7 Edge Cases to Handle

1. **Circular Dependencies**
   ```yaml
   steps:
     - name: "step_a"
       depends_on: ["step_b"]
     - name: "step_b"
       depends_on: ["step_a"]  # ERROR: Circular!
   ```
   → Detect and report error during parsing

2. **Missing Dependencies**
   ```yaml
   steps:
     - name: "step_a"
       depends_on: ["nonexistent_step"]  # ERROR!
   ```
   → Validate all dependencies exist

3. **Variable Not Defined**
   ```yaml
   steps:
     - name: "step_a"
       endpoint: "GET /users/${undefined_var}"
   ```
   → Clear error message with variable name and location

4. **Extraction Failure**
   ```yaml
   extract:
     user_id: "$.nonexistent.path"
   ```
   → Option to fail or use null/default

5. **Timeout During Polling**
   → Execute on_timeout action, include partial results

6. **Teardown Failure**
   → Log but continue with remaining teardown steps

7. **Loop Over Empty Array**
   → Skip step or execute zero times

### 1.8 Auto-Generated Workflows

Provide a feature to auto-generate basic CRUD workflows from OpenAPI:

```bash
autotest workflow generate --from-spec ./openapi.yaml
```

**Detection Logic:**
1. Group endpoints by resource path (e.g., `/users`, `/users/{id}`)
2. Identify CRUD operations:
   - POST (no ID) → Create
   - GET (with ID) → Read
   - PUT/PATCH (with ID) → Update
   - DELETE (with ID) → Delete
   - GET (no ID) → List
3. Generate workflow with proper ordering and ID extraction

---

## Feature 2: YAML Config System

### 2.1 What to Build

A unified configuration system that:
- Consolidates all tool settings in one YAML file
- Supports environment-specific overrides
- Provides inheritance and composition
- Validates configuration on load
- Supports environment variable substitution
- Integrates with CLI (CLI args override config)
- Provides sensible defaults

### 2.2 Problem This Solves

**Current State:**
- Settings scattered across CLI flags
- Hard to replicate test configurations
- No way to share settings across team
- Environment switching requires different commands
- Complex configurations need long CLI commands

**Desired State:**
- Single `api-tester.yaml` file for all settings
- Check configuration into version control
- Easy environment switching
- Team-shared base configurations with personal overrides

### 2.3 Configuration Schema

#### Complete Configuration Structure

```yaml
# api-tester.yaml - Complete Configuration File

#═══════════════════════════════════════════════════════════════════
# METADATA & INHERITANCE
#═══════════════════════════════════════════════════════════════════

# Configuration version (for future migrations)
config_version: "1.0"

# Inherit from base configuration(s)
extends:
  - ./configs/base.yaml
  - ./configs/team-defaults.yaml

# Configuration profile name
profile: "development"

#═══════════════════════════════════════════════════════════════════
# API SPECIFICATION
#═══════════════════════════════════════════════════════════════════

api:
  # OpenAPI specification source
  spec:
    # Source type: url, file, or inline
    type: "url"  # url | file
    path: "https://api.example.com/openapi.json"
    # For file type:
    # type: "file"
    # path: "./specs/openapi.yaml"
    
  # Base URL for API requests
  base_url: "https://api.example.com/v1"
  
  # API name (for reports, overrides OpenAPI info.title)
  name: "Example API"
  
  # API version being tested
  version: "1.0.0"

#═══════════════════════════════════════════════════════════════════
# AUTHENTICATION
#═══════════════════════════════════════════════════════════════════

auth:
  # Default authentication method
  default: "bearer"
  
  # Authentication methods (can define multiple)
  methods:
    bearer:
      type: "bearer"
      token: "${env:API_TOKEN}"
      # Or from file
      # token_file: "./secrets/token.txt"
      
    oauth2:
      type: "oauth2"
      flow: "client_credentials"  # client_credentials | password | authorization_code
      token_url: "https://auth.example.com/oauth/token"
      client_id: "${env:OAUTH_CLIENT_ID}"
      client_secret: "${env:OAUTH_CLIENT_SECRET}"
      scopes:
        - "read"
        - "write"
      # Token refresh settings
      refresh_buffer_seconds: 60
      
    basic:
      type: "basic"
      username: "${env:API_USERNAME}"
      password: "${env:API_PASSWORD}"
      
    api_key:
      type: "api_key"
      key: "${env:API_KEY}"
      header: "X-API-Key"  # or query parameter
      # in: "header"  # header | query
      
    custom:
      type: "custom"
      # Custom auth hook (Python file)
      hook: "./auth/custom_auth.py"
      
  # Endpoint-specific authentication
  endpoints:
    - pattern: "/admin/*"
      method: "oauth2"
      scopes: ["admin"]
      
    - pattern: "/public/*"
      method: null  # No auth for public endpoints
      
    - pattern: "/webhooks/*"
      method: "api_key"

#═══════════════════════════════════════════════════════════════════
# REQUEST SETTINGS
#═══════════════════════════════════════════════════════════════════

request:
  # Default timeout for all requests (seconds)
  timeout: 30
  
  # Default headers added to all requests
  headers:
    User-Agent: "API-Tester/1.0"
    Accept: "application/json"
    X-Request-ID: "${uuid}"
    
  # Follow redirects
  follow_redirects: true
  max_redirects: 5
  
  # SSL verification
  verify_ssl: true
  # Custom CA bundle
  # ca_bundle: "./certs/ca-bundle.crt"
  
  # Client certificate (mTLS)
  # client_cert:
  #   cert: "./certs/client.crt"
  #   key: "./certs/client.key"
  
  # Proxy settings
  # proxy:
  #   http: "http://proxy.example.com:8080"
  #   https: "http://proxy.example.com:8080"
  
  # Rate limiting
  rate_limit:
    enabled: true
    requests_per_second: 10
    burst: 20
    
  # Retry settings
  retry:
    enabled: true
    max_attempts: 3
    backoff:
      type: "exponential"  # fixed | exponential
      initial: 1  # seconds
      max: 30
    retry_on:
      - 429  # Too Many Requests
      - 503  # Service Unavailable
      - 504  # Gateway Timeout

#═══════════════════════════════════════════════════════════════════
# TEST GENERATION (autotest Settings)
#═══════════════════════════════════════════════════════════════════

generation:
  # Maximum test cases per endpoint
  max_examples: 100
  
  # Test generation mode
  mode: "all"  # positive | negative | all
  
  # Phases to run
  phases:
    - examples    # Use OpenAPI examples
    - coverage    # Boundary values
    - fuzzing     # Random generation
    - stateful    # Multi-step sequences
    
  # Deterministic mode (reproducible tests)
  deterministic: false
  seed: null  # Set for reproducibility
  
  # Test case shrinking (find minimal failure)
  shrinking: true
  
  # Unique test cases only
  unique: true

#═══════════════════════════════════════════════════════════════════
# VALIDATION & CHECKS
#═══════════════════════════════════════════════════════════════════

validation:
  # Built-in checks to run
  checks:
    - not_a_server_error
    - status_code_conformance
    - content_type_conformance
    - response_schema_conformance
    - response_headers_conformance
    - negative_data_rejection
    
  # Custom checks (Python files)
  custom_checks:
    - "./checks/business_rules.py"
    - "./checks/security.py"
    
  # Schema validation settings
  schema:
    # Strict mode (fail on additional properties)
    strict: false
    # Ignore specific schema errors
    ignore_errors:
      - "additionalProperties"

#═══════════════════════════════════════════════════════════════════
# ID EXTRACTION (Phase 1 Feature)
#═══════════════════════════════════════════════════════════════════

id_extraction:
  enabled: true
  
  # Detection strategies
  strategies:
    - path_parameter_matching
    - common_id_fields
    - schema_hints
    - response_headers
    - openapi_links
    
  # Custom ID patterns
  patterns:
    - "id"
    - "*_id"
    - "*Id"
    - "uuid"
    - "*_uuid"
    
  # Explicit mappings
  mappings:
    "POST /users":
      extract: "id"
      inject_to:
        - "userId"
        - "user_id"
        
  # Injection behavior
  injection:
    prefer: "latest"  # latest | random | first
    fallback_to_generated: true
    
  # Persistence
  persistence:
    enabled: false
    path: "./.id-store.json"

#═══════════════════════════════════════════════════════════════════
# WORKFLOWS (Phase 2 Feature)
#═══════════════════════════════════════════════════════════════════

workflows:
  # Directory containing workflow files
  directory: "./workflows"
  
  # Workflows to run (empty = all)
  include:
    - "user_crud"
    - "order_processing"
    
  # Workflows to skip
  exclude:
    - "deprecated_*"
    
  # Run workflows by tags
  tags:
    - "critical"
    - "smoke"
    
  # Workflow execution settings
  settings:
    # Run workflows in parallel
    parallel: false
    max_parallel: 4
    
    # Global workflow timeout
    timeout: 600  # seconds
    
    # Stop on first workflow failure
    fail_fast: false
    
    # Cleanup on failure
    cleanup_on_failure: true

#═══════════════════════════════════════════════════════════════════
# ENDPOINT FILTERING
#═══════════════════════════════════════════════════════════════════

endpoints:
  # Include only these endpoints
  include:
    - "/users/*"
    - "/orders/*"
    
  # Exclude these endpoints
  exclude:
    - "/internal/*"
    - "/health"
    - "/metrics"
    
  # Include by tag
  include_tags:
    - "public"
    - "v1"
    
  # Exclude by tag
  exclude_tags:
    - "deprecated"
    - "internal"
    
  # Include by operation ID
  include_operations:
    - "createUser"
    - "getUser"
    
  # Method filtering
  methods:
    - GET
    - POST
    - PUT
    - DELETE
    # Exclude: PATCH, OPTIONS, HEAD
    
  # Endpoint-specific settings
  overrides:
    - pattern: "/users/*"
      settings:
        max_examples: 200
        timeout: 60
        
    - pattern: "/batch/*"
      settings:
        timeout: 120
        rate_limit:
          requests_per_second: 1

#═══════════════════════════════════════════════════════════════════
# EXECUTION
#═══════════════════════════════════════════════════════════════════

execution:
  # Number of parallel workers
  workers: "auto"  # auto | number
  
  # Overall test timeout
  timeout: 3600  # 1 hour
  
  # Stop on first failure
  fail_fast: false
  
  # Verbose output
  verbose: false
  
  # Dry run (don't execute, just show what would run)
  dry_run: false

#═══════════════════════════════════════════════════════════════════
# REPORTING (Phase 1 Feature)
#═══════════════════════════════════════════════════════════════════

reporting:
  # Output directory for all reports
  output_dir: "./reports"
  
  # HTML report settings
  html:
    enabled: true
    path: "${output_dir}/report.html"
    title: "API Test Report - ${api.name}"
    include_passed_details: false
    max_body_size: 10240  # 10KB
    sanitize_headers:
      - "Authorization"
      - "X-API-Key"
      - "Cookie"
      
  # JUnit XML report (for CI/CD)
  junit:
    enabled: true
    path: "${output_dir}/junit.xml"
    
  # JSON report (machine-readable)
  json:
    enabled: true
    path: "${output_dir}/report.json"
    pretty: true
    
  # VCR cassette (request/response recording)
  vcr:
    enabled: false
    path: "${output_dir}/cassette.yaml"
    
  # HAR file
  har:
    enabled: false
    path: "${output_dir}/requests.har"
    
  # Console output
  console:
    # Progress style
    style: "rich"  # simple | rich | quiet
    # Show request/response on failure
    show_failures: true
    # Color output
    color: true

#═══════════════════════════════════════════════════════════════════
# DATA GENERATION
#═══════════════════════════════════════════════════════════════════

data:
  # Faker locale
  locale: "en_US"
  
  # Custom data generators
  generators:
    email: "faker:email"
    phone: "faker:phone_number"
    username: "faker:user_name"
    
  # Field-specific overrides
  overrides:
    # Always use specific value
    "*.country": "US"
    "*.currency": "USD"
    
    # Pattern-based
    "User.email": "test-${random:8}@example.com"
    "Order.reference": "ORD-${timestamp}-${random:4}"
    
  # Fixtures (predefined test data)
  fixtures:
    directory: "./fixtures"
    files:
      - "users.yaml"
      - "products.yaml"

#═══════════════════════════════════════════════════════════════════
# HOOKS & EXTENSIONS
#═══════════════════════════════════════════════════════════════════

hooks:
  # Python hook files
  files:
    - "./hooks/auth_hooks.py"
    - "./hooks/data_hooks.py"
    - "./hooks/validation_hooks.py"
    
  # Specific hook registrations
  before_call:
    - "hooks.auth_hooks.add_signature"
  after_call:
    - "hooks.validation_hooks.check_response_time"

#═══════════════════════════════════════════════════════════════════
# ENVIRONMENTS
#═══════════════════════════════════════════════════════════════════

# Environment-specific overrides
environments:
  development:
    api:
      base_url: "http://localhost:8080"
    auth:
      default: "basic"
      methods:
        basic:
          username: "dev_user"
          password: "dev_pass"
    request:
      verify_ssl: false
    generation:
      max_examples: 10
      
  staging:
    api:
      base_url: "https://staging-api.example.com"
    auth:
      default: "oauth2"
    request:
      verify_ssl: true
      
  production:
    api:
      base_url: "https://api.example.com"
    auth:
      default: "oauth2"
    # Safety: read-only in production
    endpoints:
      methods:
        - GET
    generation:
      mode: "positive"  # No negative testing in prod

# Active environment (can be overridden via CLI or env var)
environment: "${env:TEST_ENV:development}"
```

### 2.4 Configuration Features Deep Dive

#### 2.4.1 Configuration Inheritance

Support multiple levels of inheritance:

```yaml
# base.yaml (team shared)
config_version: "1.0"
api:
  name: "Company API"
request:
  timeout: 30
  headers:
    User-Agent: "Company-Tester/1.0"
reporting:
  html:
    enabled: true

---
# project.yaml
extends:
  - ./base.yaml
  
api:
  spec:
    path: "./openapi.yaml"
  base_url: "https://api.example.com"

---
# local.yaml (personal overrides, gitignored)
extends:
  - ./project.yaml
  
auth:
  methods:
    bearer:
      token: "my-personal-token"
```

**Inheritance Rules:**
- Later files override earlier
- Deep merge for objects
- Replace for arrays (unless using special merge syntax)
- Environment variables resolved at load time

#### 2.4.2 Environment Variable Substitution

```yaml
# Basic substitution
api_key: "${env:API_KEY}"

# With default value
api_key: "${env:API_KEY:default_key}"

# Nested in strings
base_url: "https://${env:API_HOST:localhost}:${env:API_PORT:8080}"

# In arrays
scopes:
  - "${env:OAUTH_SCOPE_1}"
  - "${env:OAUTH_SCOPE_2}"
```

#### 2.4.3 File References

```yaml
# Include entire file content
auth:
  methods:
    bearer:
      token_file: "./secrets/token.txt"
      
# Include YAML section
endpoints:
  include: "${file:./configs/endpoints.yaml}"
  
# Include JSON
fixtures:
  users: "${json:./fixtures/users.json}"
```

#### 2.4.4 Dynamic Values

```yaml
# Timestamp
request:
  headers:
    X-Timestamp: "${now:format=ISO}"
    
# Random values
data:
  overrides:
    "User.email": "test-${random:8}@test.com"
    
# UUID
request:
  headers:
    X-Request-ID: "${uuid}"
```

#### 2.4.5 Conditional Configuration

```yaml
# Include section only if condition is true
reporting:
  html:
    enabled: "${env:CI:false}"  # Enable only in CI
    
# Different values based on environment
api:
  base_url: "${if:${env:CI}, 'https://staging.api.com', 'http://localhost:8080'}"
```

### 2.5 Implementation Approach

#### Step 1: Configuration Schema Definition
**Location:** Create `autotest/config/schema.py`

**Responsibilities:**
- Define complete configuration schema using Pydantic
- All fields with types, defaults, and validation
- Nested model definitions

**Key Models:**

```
Config
├── config_version: str
├── extends: List[str]
├── profile: Optional[str]
├── api: ApiConfig
├── auth: AuthConfig
├── request: RequestConfig
├── generation: GenerationConfig
├── validation: ValidationConfig
├── id_extraction: IdExtractionConfig
├── workflows: WorkflowsConfig
├── endpoints: EndpointsConfig
├── execution: ExecutionConfig
├── reporting: ReportingConfig
├── data: DataConfig
├── hooks: HooksConfig
├── environments: Dict[str, EnvironmentOverride]
├── environment: str
```

#### Step 2: Configuration Loader
**Location:** Create `autotest/config/loader.py`

**Responsibilities:**
- Load YAML files
- Resolve `extends` inheritance
- Merge configurations
- Apply environment overrides
- Resolve environment variables
- Validate against schema

**Loading Flow:**

```
ConfigLoader.load(path, env=None):
│
├─→ Read YAML file
├─→ Check for 'extends'
│   └─→ Recursively load parent configs
│       └─→ Merge parent into current (deep merge)
│
├─→ Resolve ${env:...} variables
├─→ Resolve ${file:...} includes
├─→ Resolve ${now}, ${uuid}, ${random}
│
├─→ Apply environment overrides if env specified
│   └─→ Deep merge environments.{env} into config
│
├─→ Validate against schema
├─→ Apply defaults for missing values
│
└─→ Return Config object
```

#### Step 3: Variable Resolver
**Location:** Create `autotest/config/resolver.py`

**Responsibilities:**
- Parse ${...} expressions
- Resolve environment variables
- Handle defaults
- File inclusions
- Dynamic value generation

**Supported Syntax:**

```python
PATTERNS = {
    r'\$\{env:(\w+)(?::([^}]*))?\}': resolve_env,        # ${env:VAR:default}
    r'\$\{file:([^}]+)\}': resolve_file,                  # ${file:path}
    r'\$\{json:([^}]+)\}': resolve_json,                  # ${json:path}
    r'\$\{now(?::format=([^}]+))?\}': resolve_timestamp,  # ${now:format=ISO}
    r'\$\{uuid\}': resolve_uuid,                          # ${uuid}
    r'\$\{random(?::(\w+=\w+(?:,\w+=\w+)*))?\}': resolve_random,  # ${random:length=8}
    r'\$\{if:([^,]+),([^,]+),([^}]+)\}': resolve_conditional,  # ${if:cond,then,else}
}
```

#### Step 4: Configuration Merger
**Location:** Create `autotest/config/merger.py`

**Responsibilities:**
- Deep merge dictionaries
- Handle array merge strategies
- Preserve types during merge

**Merge Strategies:**

```yaml
# Default: replace arrays
list1: [1, 2, 3]
# Merged with
list1: [4, 5]
# Result: [4, 5]

# Special: append to array
list1:
  $append:
    - 4
    - 5
# Result: [1, 2, 3, 4, 5]

# Special: prepend to array
list1:
  $prepend:
    - 0
# Result: [0, 1, 2, 3]

# Special: merge arrays (unique)
list1:
  $merge: [2, 4, 5]
# Result: [1, 2, 3, 4, 5]
```

#### Step 5: Configuration Validator
**Location:** Create `autotest/config/validator.py`

**Responsibilities:**
- Validate against Pydantic schema
- Custom validation rules
- Clear error messages with paths
- Suggest fixes for common errors

**Validation Rules:**
- Required fields present
- Valid URLs
- Valid file paths exist
- Valid regex patterns
- No circular inheritance
- Environment exists if referenced

#### Step 6: CLI Integration
**Location:** Modify `autotest/cli/`

**New Behaviors:**
- Auto-detect config file (`api-tester.yaml`, `autotest.yaml`, etc.)
- `--config` flag to specify config file
- `--env` flag to select environment
- CLI args override config values
- `--no-config` to ignore config file

**Config Discovery Order:**
1. `--config <path>` if provided
2. `api-tester.yaml` in current directory
3. `autotest.yaml` in current directory
4. `.api-tester.yaml` in current directory
5. `pyproject.toml` [tool.api-tester] section
6. No config (use defaults + CLI args)

#### Step 7: Configuration Commands
**New CLI Commands:**

```bash
# Initialize new configuration
autotest config init
# Interactive wizard to create config

# Validate configuration
autotest config validate ./api-tester.yaml

# Show resolved configuration
autotest config show ./api-tester.yaml --env staging

# Show effective config (with inheritance resolved)
autotest config resolve ./api-tester.yaml

# List available environments
autotest config environments ./api-tester.yaml

# Generate config from OpenAPI spec
autotest config generate --from-spec ./openapi.yaml
```

### 2.6 Recommended Third-Party Packages

| Package | Purpose | Why This Package |
|---------|---------|------------------|
| **PyYAML** | YAML parsing | Standard, already in project |
| **Pydantic** | Schema validation | Powerful validation, already in project |
| **python-dotenv** | .env file support | Load .env files for local development |
| **deepmerge** | Deep dictionary merging | Handles complex merge strategies |
| **jsonschema** | JSON Schema validation | For config schema validation |
| **click** | CLI framework | Already used by autotest |
| **rich** | Console output | Pretty config display |
| **toml** | TOML parsing | For pyproject.toml support |

### 2.7 Edge Cases to Handle

1. **Circular Inheritance**
   ```yaml
   # a.yaml
   extends: [./b.yaml]
   
   # b.yaml
   extends: [./a.yaml]  # ERROR: Circular!
   ```
   → Detect and report with inheritance chain

2. **Missing Environment Variable**
   ```yaml
   api_key: "${env:MISSING_VAR}"
   ```
   → Error with variable name, or use default if provided

3. **File Not Found**
   ```yaml
   extends: [./nonexistent.yaml]
   ```
   → Clear error with attempted path

4. **Type Mismatch After Merge**
   ```yaml
   # base.yaml
   timeout: 30
   
   # child.yaml
   timeout: "thirty"  # ERROR: should be int
   ```
   → Validation error after merge

5. **Environment Override Non-Existent Field**
   ```yaml
   environments:
     staging:
       nonexistent_section:
         key: value
   ```
   → Warning or error depending on strict mode

6. **Self-Reference in Variables**
   ```yaml
   base_url: "https://${base_url}/v1"  # ERROR!
   ```
   → Detect and report

### 2.8 Configuration Templates

Provide starter templates for common scenarios:

```bash
autotest config init --template basic
autotest config init --template enterprise
autotest config init --template ci-cd
autotest config init --template microservices
```

**Basic Template:**
- Single API, basic auth, minimal settings

**Enterprise Template:**
- OAuth2, multiple environments, full reporting

**CI/CD Template:**
- Optimized for pipelines, JUnit output, fail-fast

**Microservices Template:**
- Multiple API specs, service-specific configs

---

## Integration Architecture

### How Both Features Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                    Configuration & Workflow Flow                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Load Configuration                                          │
│     └─→ ConfigLoader.load("api-tester.yaml", env="staging")    │
│     └─→ Resolve inheritance, env vars, validate                 │
│     └─→ Return fully resolved Config object                     │
│                                                                 │
│  2. Initialize Components with Config                           │
│     └─→ AuthManager(config.auth)                               │
│     └─→ HttpClient(config.request)                             │
│     └─→ IDExtractor(config.id_extraction)                      │
│     └─→ ReportGenerator(config.reporting)                      │
│     └─→ WorkflowEngine(config.workflows)                       │
│                                                                 │
│  3. Load Workflows                                              │
│     └─→ WorkflowLoader.load(config.workflows.directory)        │
│     └─→ Filter by include/exclude/tags                         │
│     └─→ Parse and validate workflow definitions                 │
│                                                                 │
│  4. Execute                                                     │
│     ├─→ If workflows defined:                                  │
│     │   └─→ WorkflowExecutor.run_all(workflows)               │
│     │       └─→ For each workflow:                             │
│     │           └─→ Execute steps using config settings        │
│     │                                                          │
│     └─→ If standard autotest mode:                         │
│         └─→ Run property-based tests with config               │
│                                                                 │
│  5. Generate Reports                                            │
│     └─→ Include workflow results in HTML report                │
│     └─→ Generate all configured report formats                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Driving Workflows

Workflows can reference configuration values:

```yaml
# api-tester.yaml
variables:
  default_user_role: "member"
  max_items: 100

# workflow.yaml
workflows:
  - name: "user_workflow"
    steps:
      - name: "create_user"
        endpoint: "POST /users"
        request:
          body:
            role: "${config:variables.default_user_role}"
            
      - name: "list_users"
        endpoint: "GET /users"
        request:
          query:
            limit: "${config:variables.max_items}"
```

---

## Development Roadmap

### Week 1-2: Configuration Foundation

**Milestone 1: Configuration Schema & Loader**
- [ ] Define complete Pydantic schema for configuration
- [ ] Implement basic YAML loader
- [ ] Implement environment variable resolution
- [ ] Implement file inclusion
- [ ] Write unit tests for loader
- [ ] Write schema validation tests

**Deliverable:** Can load and validate a configuration file

**Milestone 2: Configuration Inheritance & Merging**
- [ ] Implement extends/inheritance loading
- [ ] Implement deep merge logic
- [ ] Implement merge strategies for arrays
- [ ] Handle circular inheritance detection
- [ ] Write inheritance tests

**Deliverable:** Configuration inheritance fully working

### Week 3-4: Configuration Integration

**Milestone 3: Environment Support**
- [ ] Implement environment overrides
- [ ] Implement environment selection
- [ ] Add --env CLI flag
- [ ] Support TEST_ENV environment variable
- [ ] Test environment switching

**Deliverable:** Easy environment switching working

**Milestone 4: CLI Integration**
- [ ] Auto-detect configuration files
- [ ] Add --config flag
- [ ] CLI args override config values
- [ ] Implement config subcommands (init, validate, show)
- [ ] Integration tests with CLI

**Deliverable:** Full CLI integration with configuration

### Week 5-6: Workflow Foundation

**Milestone 5: Workflow Parser & Models**
- [ ] Define workflow Pydantic models
- [ ] Implement workflow YAML parser
- [ ] Implement step parser
- [ ] Implement dependency graph builder
- [ ] Validate workflow definitions
- [ ] Write parser tests

**Deliverable:** Can parse and validate workflow files

**Milestone 6: Expression Engine**
- [ ] Implement variable resolution in workflows
- [ ] Implement JSONPath extraction
- [ ] Implement faker integration
- [ ] Implement built-in functions
- [ ] Implement conditional expressions
- [ ] Write expression tests

**Deliverable:** All expressions can be parsed and evaluated

### Week 7-8: Workflow Execution

**Milestone 7: Workflow Executor**
- [ ] Implement basic step execution
- [ ] Implement dependency ordering
- [ ] Implement variable context management
- [ ] Implement data extraction
- [ ] Implement response validation
- [ ] Write executor tests

**Deliverable:** Basic workflows execute correctly

**Milestone 8: Advanced Workflow Features**
- [ ] Implement loops (count and over)
- [ ] Implement polling for async
- [ ] Implement conditional execution
- [ ] Implement setup/teardown
- [ ] Implement failure handling
- [ ] Write advanced feature tests

**Deliverable:** All workflow features working

### Week 9: Integration & Polish

**Milestone 9: Full Integration**
- [ ] Integrate workflows with configuration
- [ ] Integrate workflows with ID extraction (Phase 1)
- [ ] Integrate workflows with HTML report (Phase 1)
- [ ] Add workflow summary to reports
- [ ] Performance testing
- [ ] End-to-end tests

**Deliverable:** Both features working together

### Week 10: Documentation & Release

**Milestone 10: Documentation & Quality**
- [ ] Configuration reference documentation
- [ ] Workflow authoring guide
- [ ] Migration guide from CLI flags
- [ ] Example configurations
- [ ] Example workflows
- [ ] Full test coverage

**Deliverable:** Production-ready Phase 2

---

## File Structure (Proposed)

```
autotest/
├── config/                        # NEW: Configuration Module
│   ├── __init__.py
│   ├── schema.py                 # Pydantic models for config
│   ├── loader.py                 # Config loading logic
│   ├── resolver.py               # Variable resolution
│   ├── merger.py                 # Deep merge logic
│   ├── validator.py              # Validation rules
│   ├── templates/                # Config templates
│   │   ├── basic.yaml
│   │   ├── enterprise.yaml
│   │   ├── ci-cd.yaml
│   │   └── microservices.yaml
│   └── tests/
│       ├── test_schema.py
│       ├── test_loader.py
│       ├── test_resolver.py
│       ├── test_merger.py
│       └── test_validator.py
│
├── workflows/                     # NEW: Workflow Module
│   ├── __init__.py
│   ├── models.py                 # Workflow data models
│   ├── parser.py                 # YAML parsing
│   ├── executor.py               # Workflow execution
│   ├── expressions.py            # Expression engine
│   ├── dependency_graph.py       # Dependency resolution
│   ├── validator.py              # Response validation
│   ├── generator.py              # Auto-generate workflows
│   ├── templates/                # Workflow templates
│   │   ├── crud_basic.yaml
│   │   └── crud_nested.yaml
│   └── tests/
│       ├── test_models.py
│       ├── test_parser.py
│       ├── test_executor.py
│       ├── test_expressions.py
│       └── test_dependency_graph.py
│
├── cli/
│   ├── ... (existing)
│   ├── commands/
│   │   ├── config.py             # NEW: config subcommand
│   │   └── workflow.py           # NEW: workflow subcommand
│   └── options.py                # MODIFY: Add config options
│
├── reporting/                     # FROM Phase 1
│   └── ...                       # Add workflow reporting
│
└── extraction/                    # FROM Phase 1
    └── ...
```

---

## Success Criteria

### YAML Config System
- [ ] Single file contains all configuration
- [ ] Inheritance works correctly (multi-level)
- [ ] Environment variables resolve correctly
- [ ] Environment switching works
- [ ] CLI args override config
- [ ] Auto-detection of config files works
- [ ] Clear error messages for invalid config
- [ ] Migration path from CLI-only usage

### Workflow Definitions
- [ ] CRUD workflows execute in correct order
- [ ] Data flows between steps correctly
- [ ] Conditional execution works
- [ ] Loops execute correctly
- [ ] Polling for async operations works
- [ ] Setup/teardown always runs
- [ ] Failure handling works correctly
- [ ] Workflow results appear in HTML report

### Integration
- [ ] Config drives workflow behavior
- [ ] Phase 1 features work with config
- [ ] No regression in autotest functionality
- [ ] Comprehensive documentation
- [ ] Example configs and workflows

---

## Appendix: Example Configurations

### Minimal Configuration

```yaml
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
      token: "${env:API_TOKEN}"
```

### CI/CD Configuration

```yaml
config_version: "1.0"
profile: "ci"

api:
  spec:
    type: url
    path: "${env:API_SPEC_URL}"
  base_url: "${env:API_BASE_URL}"

auth:
  default: oauth2
  methods:
    oauth2:
      type: oauth2
      flow: client_credentials
      token_url: "${env:OAUTH_TOKEN_URL}"
      client_id: "${env:OAUTH_CLIENT_ID}"
      client_secret: "${env:OAUTH_CLIENT_SECRET}"

generation:
  max_examples: 50
  mode: all

execution:
  workers: auto
  fail_fast: true

reporting:
  output_dir: "./test-results"
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
```

### Multi-Service Configuration

```yaml
config_version: "1.0"
profile: "microservices"

# Base settings inherited by all services
request:
  timeout: 30
  headers:
    X-Correlation-ID: "${uuid}"

# Service-specific configurations
services:
  user-service:
    api:
      spec:
        path: ./specs/user-service.yaml
      base_url: http://users.local:8001
    endpoints:
      include:
        - "/users/*"
        
  order-service:
    api:
      spec:
        path: ./specs/order-service.yaml
      base_url: http://orders.local:8002
    endpoints:
      include:
        - "/orders/*"
        
  payment-service:
    api:
      spec:
        path: ./specs/payment-service.yaml
      base_url: http://payments.local:8003
    endpoints:
      include:
        - "/payments/*"

# Cross-service workflows
workflows:
  directory: ./workflows/integration
  tags:
    - integration
```

---

## Appendix: Example Workflows

### Basic CRUD Workflow

```yaml
workflows:
  - name: user_crud
    description: "Basic user CRUD operations"
    
    steps:
      - name: create_user
        endpoint: POST /users
        request:
          body:
            name: "${faker:name}"
            email: "${faker:email}"
        expect:
          status: [201]
        extract:
          user_id: $.id
          
      - name: get_user
        endpoint: GET /users/${user_id}
        depends_on: [create_user]
        expect:
          status: [200]
          
      - name: update_user
        endpoint: PUT /users/${user_id}
        depends_on: [get_user]
        request:
          body:
            name: "Updated Name"
        expect:
          status: [200]
          
      - name: delete_user
        endpoint: DELETE /users/${user_id}
        depends_on: [update_user]
        expect:
          status: [204]
```

### E-Commerce Order Workflow

```yaml
workflows:
  - name: complete_order
    description: "Full order workflow from cart to delivery"
    
    variables:
      quantity: 2
      
    setup:
      - name: get_available_product
        endpoint: GET /products
        request:
          query:
            in_stock: true
            limit: 1
        extract:
          product_id: $.items[0].id
          product_price: $.items[0].price
          
    steps:
      - name: create_cart
        endpoint: POST /carts
        expect:
          status: [201]
        extract:
          cart_id: $.id
          
      - name: add_to_cart
        endpoint: POST /carts/${cart_id}/items
        depends_on: [create_cart]
        request:
          body:
            product_id: "${product_id}"
            quantity: "${quantity}"
        expect:
          status: [200]
          body:
            total: "${product_price * quantity}"
            
      - name: checkout
        endpoint: POST /carts/${cart_id}/checkout
        depends_on: [add_to_cart]
        request:
          body:
            payment_method: "credit_card"
            shipping_address:
              street: "${faker:street_address}"
              city: "${faker:city}"
              zip: "${faker:postcode}"
        expect:
          status: [201]
        extract:
          order_id: $.order_id
          
      - name: wait_for_processing
        endpoint: GET /orders/${order_id}
        depends_on: [checkout]
        poll:
          interval: 2
          timeout: 30
          until:
            body:
              status: ["processing", "shipped"]
              
      - name: verify_order
        endpoint: GET /orders/${order_id}
        depends_on: [wait_for_processing]
        expect:
          status: [200]
          custom:
            - "response.body.items.length == 1"
            - "response.body.items[0].quantity == ${quantity}"
            
    teardown:
      - name: cancel_order
        endpoint: POST /orders/${order_id}/cancel
        condition: "${order_id} != null"
        ignore_failure: true
```

---

*This specification document serves as the blueprint for Phase 2 development. It builds upon Phase 1 features and provides a comprehensive configuration and workflow system.*

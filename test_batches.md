# CLI Test Batches

Run tests in batches of 10 to isolate failures.

## Batch 1 (test_cassettes.py - first 10)
```powershell
pytest test/cli/test_cassettes.py::test_cassette_path_template -v
pytest test/cli/test_cassettes.py::test_cassette_preserve_exact -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_all -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_with_replacement -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_headers_only -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_body_only -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_cookies_only -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_query_only -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_path_only -v
pytest test/cli/test_cassettes.py::test_cassette_sanitize_multiple -v
```

## Batch 2 (test_cassettes.py - remaining)
```powershell
pytest "test/cli/test_cassettes.py" -v
```

## Batch 3 (test_checks.py)
```powershell
pytest "test/cli/test_checks.py" -v
```

## Batch 4 (test_commands.py - first 10)
```powershell
pytest "test/cli/test_commands.py::test_commands_help" -v
pytest "test/cli/test_commands.py::test_run_subprocess" -v
pytest "test/cli/test_commands.py::test_run_as_module" -v
pytest "test/cli/test_commands.py::test_run_output[args0]" -v
pytest "test/cli/test_commands.py::test_run_output[args1]" -v
pytest "test/cli/test_commands.py::test_run_output[args2]" -v
pytest "test/cli/test_commands.py::test_run_output[args3]" -v
pytest "test/cli/test_commands.py::test_run_output[args4]" -v
pytest "test/cli/test_commands.py::test_run_output[args5]" -v
pytest "test/cli/test_commands.py::test_run_output[args6]" -v
```

## Batch 5 (test_commands.py - 11-20)
```powershell
pytest "test/cli/test_commands.py::test_run_output[args7]" -v
pytest "test/cli/test_commands.py::test_run_output[args8]" -v
pytest "test/cli/test_commands.py::test_run_output[args9]" -v
pytest "test/cli/test_commands.py::test_run_output[args10]" -v
pytest "test/cli/test_commands.py::test_run_output[args11]" -v
pytest "test/cli/test_commands.py::test_run_output[args12]" -v
pytest "test/cli/test_commands.py::test_run_output[args13]" -v
pytest "test/cli/test_commands.py::test_run_output[args14]" -v
pytest "test/cli/test_commands.py::test_run_output[args15]" -v
pytest "test/cli/test_commands.py::test_run_output[args16]" -v
```

## Run by Test File (Recommended)

### test_cassettes.py (34 tests)
```powershell
pytest test/cli/test_cassettes.py -v
```

### test_checks.py (30 tests)
```powershell
pytest test/cli/test_checks.py -v
```

### test_commands.py (200 tests)
```powershell
pytest test/cli/test_commands.py -v
```

### test_config_display.py (2 tests)
```powershell
pytest test/cli/test_config_display.py -v
```

### test_crashes.py (4 tests)
```powershell
pytest test/cli/test_crashes.py -v
```

### test_deserializers.py (6 tests)
```powershell
pytest test/cli/test_deserializers.py -v
```

### test_extra_data_sources.py (3 tests)
```powershell
pytest test/cli/test_extra_data_sources.py -v
```

### test_help_colors.py (14 tests)
```powershell
pytest test/cli/test_help_colors.py -v
```

### test_hooks.py (3 tests)
```powershell
pytest test/cli/test_hooks.py -v
```

### test_junitxml.py (13 tests)
```powershell
pytest test/cli/test_junitxml.py -v
```

### test_negative_metadata.py (6 tests)
```powershell
pytest test/cli/test_negative_metadata.py -v
```

### test_nested_ref_responses.py (2 tests)
```powershell
pytest test/cli/test_nested_ref_responses.py -v
```

### test_options.py (1 test)
```powershell
pytest test/cli/test_options.py -v
```

### test_targeted.py (3 tests)
```powershell
pytest test/cli/test_targeted.py -v
```

### test_validation.py (14 tests)
```powershell
pytest test/cli/test_validation.py -v
```

### test_warnings.py (7 tests)
```powershell
pytest test/cli/test_warnings.py -v
```

---

## Quick Commands

### Run all CLI tests
```powershell
pytest test/cli/ -v
```

### Run with short traceback
```powershell
pytest test/cli/ -v --tb=short
```

### Run and update snapshots
```powershell
pytest test/cli/ -v --snapshot-update
```

### Run specific test by name pattern
```powershell
pytest test/cli/ -v -k "auth"
```

### Run first N tests
```powershell
pytest test/cli/ -v --maxfail=10
```

### Run tests in parallel (faster)
```powershell
pytest test/cli/ -v -n auto
```

# Test Suites

## Command	Description
pytest test/auth/ -v	Authentication tests
pytest test/config/ -v	Configuration tests
pytest test/core/ -v	Core functionality tests
pytest test/coverage/ -v	Coverage-related tests
pytest test/engine/ -v	Engine tests
pytest test/hooks/ -v	Hooks tests
pytest test/filters/ -v	Filter tests
pytest test/loaders/ -v	Loader tests
pytest test/openapi/ -v	OpenAPI tests
pytest test/pytest/ -v	Pytest integration tests
pytest test/python/ -v	Python-specific tests
pytest test/contrib/ -v	Contrib module tests
pytest test/_pytest/ -v	Pytest markers tests

## Individual Test Files (Root of test/)

## Command	Description
pytest test/test_app.py -v	App tests
pytest test/test_asgi.py -v	ASGI transport tests
pytest test/test_async.py -v	Async tests
pytest test/test_wsgi.py -v	WSGI transport tests
pytest test/test_hypothesis.py -v	Hypothesis tests
pytest test/test_parameters.py -v	Parameter tests
pytest test/test_parametrization.py -v	Parametrization tests
pytest test/test_schemas.py -v	Schema tests
pytest test/test_serialization.py -v	Serialization tests
pytest test/test_stateful.py -v	Stateful testing tests
pytest test/test_dereferencing.py -v	Dereferencing tests
pytest test/test_filters.py -v	Filter tests
pytest test/test_lazy.py -v	Lazy loading tests
pytest test/test_petstore.py -v	Petstore example tests

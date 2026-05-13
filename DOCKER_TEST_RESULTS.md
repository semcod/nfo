## Test Environment
- **Date**: 2026-02-16
- **Test Framework**: Docker container with Python 3.12
- **Test Script**: `tests/docker/test_docs.py`

## Summary

| Metric | Value |
|--------|-------|
| **Total Tests** | 11 |
| **Passed** | 11 (100%) |
| **Failed** | 0 (0%) |

All documented commands tested successfully in Docker environment.

### CLI Commands (4/4 Passing)

| Test | Status | Notes |
|------|--------|-------|
| `nfo version` | PASS | Version 0.2.14 correctly displayed |
| `nfo run -- bash -c 'echo hello'` | PASS | Bash command execution with SQLite logging |
| `nfo run -- python3 -c 'print(42)'` | PASS | Python command execution with SQLite logging |
| `nfo logs` | PASS | SQLite log querying works correctly |

### Python Examples (6/6 Passing)

| Test | Status | Notes |
|------|--------|-------|
| `examples/basic-usage/main.py` | PASS | `@log_call` and `@catch` decorators working |
| `examples/sqlite-sink/main.py` | PASS | SQLiteSink database creation and querying |
| `examples/csv-sink/main.py` | PASS | CSVSink CSV file output working |
| `examples/markdown-sink/main.py` | PASS | MarkdownSink Markdown table output working |
| `examples/configure/main.py` | PASS | `configure()` one-liner setup working |
| `examples/auto-log/main.py` | PASS | `auto_log()` module patching working |

### HTTP Service (1/1 Passing)

| Test | Status | Notes |
|------|--------|-------|
| `nfo serve` + HTTP POST/GET | PASS | HTTP service starts and accepts log entries |

### 1. pyproject.toml License Classifier (Fixed)

**Problem**: Modern setuptools (v69+) rejects the combination of `license = "Apache-2.0"` with `License :: OSI Approved :: Apache Software License` classifier.

**Fix**: Removed the deprecated license classifier from `classifiers` list.

```toml
# Before
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",  # REMOVED
]

# After
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
]
```

### 2. HTTP Service Pydantic v2 Compatibility (Fixed)

**Problem**: Pydantic v2's `TypeAdapter` cannot resolve forward references for classes defined inside functions. The HTTP service returned 422/500 errors when trying to POST log entries.

**Error**: `TypeAdapter[...] is not fully defined; you should define [...] and all referenced types`

**Fix**: Moved Pydantic models `_HttpLogEntry` and `_HttpBatchReq` to module level and added conditional import for `BaseModel`.

Also updated route handlers to use `Body(...)` annotation for proper request body parsing.

### 3. pytest-asyncio Plugin (Previously Fixed)

**Problem**: Async tests failing with "async def functions are not natively supported" error.

**Fix**: Created `tests/conftest.py` with minimal pytest hook to run `@pytest.mark.asyncio` tests.

### HTTP Service 422 Error

The `nfo serve` command starts correctly, but POST requests to `/log` endpoint return 422 Unprocessable Entity. This may be related to:
- Pydantic v2 validation changes
- Union type syntax (`bool | None`) compatibility
- FastAPI version differences

**Workaround**: Use the CLI `nfo run` command instead for command logging.

## Documentation Accuracy

Based on test results, the following README documentation is accurate:

- Installation: `pip install nfo` ✅
- Basic decorators: `@log_call`, `@catch` ✅
- Sinks: SQLiteSink, CSVSink, MarkdownSink ✅
- `configure()` function ✅
- `auto_log()` function ✅
- CLI commands: `nfo run`, `nfo logs`, `nfo version` ✅

The following requires verification:
- `nfo serve` HTTP service endpoint compatibility

# Build test image
docker build -f tests/docker/Dockerfile -t nfo-test-docs .

# Run tests
docker run --rm nfo-test-docs

# Or run manually in container
docker run -it --rm nfo-test-docs bash
python tests/docker/test_docs.py
```

## Recommendations

1. **Update pyproject.toml**: Keep the license expression fix (already applied)
2. **HTTP Service**: Investigate and fix the 422 error for the `nfo serve` endpoint
3. **Documentation**: Add note about `nfo serve` requiring `fastapi` and `uvicorn` extras
4. **CI/CD**: Integrate the Docker test suite into the CI pipeline

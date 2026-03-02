## [0.2.18] - 2026-03-02

### Summary

refactor(build): code analysis engine

### Docs

- docs: update README
- docs: update context.md

### Ci

- config: update ci.yml

### Other

- update nfo/configure.py
- update nfo/decorators.py
- update nfo/decorators/__init__.py
- update nfo/decorators/_catch.py
- update nfo/decorators/_core.py
- update nfo/decorators/_decision.py
- update nfo/decorators/_extract.py
- update nfo/decorators/_log_call.py
- update nfo/log_flow.py
- update project/analysis.toon
- ... and 3 more


## [0.2.16] - 2026-02-18

### Summary

fix(nfo): deep code analysis engine with 5 supporting modules

### Other

- update nfo/__init__.py
- update nfo/fastapi_middleware.py


## [0.2.15] - 2026-02-18

### Summary

feat(tests): multi-language support with 3 supporting modules

### Other

- update demo/tests/test_demo.py
- update nfo/__init__.py
- update nfo/tests/test_nfo.py


## [0.2.14] - 2026-02-16

### Summary

feat(tests): configuration management system

### Test

- update tests/conftest.py
- update tests/test_log_flow.py

### Build

- update pyproject.toml

### Other

- update nfo/__init__.py
- update nfo/log_flow.py


## [0.2.13] - 2026-02-15

### Summary

feat(tests): deep code analysis engine

### Test

- update tests/test_decision_log.py
- update tests/test_pipeline_sink.py


## [0.2.12] - 2026-02-15

### Summary

fix(docs): deep code analysis engine with 6 supporting modules

### Test

- update tests/test_pipeline_sink.py

### Other

- update nfo/__init__.py
- update nfo/decorators.py
- update nfo/pipeline_sink.py
- update project.functions.toon
- update project.toon


## [0.3.1] - 2026-02-15

### Summary

feat(pipeline): PipelineSink, @decision_log, global auto_extract_meta

### Added

- **`PipelineSink`** (`nfo/pipeline_sink.py`) — groups LogEntry objects by
  `pipeline_run_id` and renders pipeline ticks as box-drawing terminal blocks
  with step timings, metrics, decisions, costs, and error context.
- **`@decision_log`** decorator (`nfo/decorators.py`) — logs conditional
  decisions with structured `decision`/`reason` fields in `entry.extra`.
- **Global `auto_extract_meta`** — `_maybe_extract()` in decorators now
  falls back to the global `auto_extract_meta` flag from `configure()`,
  so all `@log_call` sites automatically extract metadata for large args
  without per-decorator changes.
- `get_global_auto_extract_meta()` in `nfo/configure.py`.
- Exports: `PipelineSink`, `decision_log` added to `__init__.py` and `__all__`.

### Test

- 23 new tests in `tests/test_pipeline_sink.py` (basic, rendering, color,
  timeout, multi-run, footer, delegate).
- Full suite: 296 passed.


## [0.2.11] - 2026-02-15

### Summary

feat(config): configuration management system

### Other

- update nfo/configure.py
- update nfo/decorators.py


## [0.2.10] - 2026-02-15

### Summary

refactor(config): CLI interface improvements

### Test

- update tests/test_click_integration.py

### Build

- update pyproject.toml

### Other

- update project.functions.toon
- update project.toon


## [0.2.9] - 2026-02-15

### Summary

refactor(goal): CLI interface improvements

### Docs

- docs: update README

### Test

- update tests/test_click_integration.py
- update tests/test_terminal.py

### Other

- update examples/click-integration/demo_basic.py
- update examples/click-integration/demo_configure.py
- update examples/click-integration/demo_formats.py
- update nfo/__init__.py
- update nfo/click.py
- update nfo/configure.py
- update nfo/terminal.py
- update project.functions.toon
- update project.toon


## [0.3.0] - 2026-02-15

### Summary

feat(meta): Binary data logging strategy — log metadata instead of raw data

### Added

- **`ThresholdPolicy`** (`nfo/meta.py`) — size-based policy deciding when to log full data vs extracted metadata; configurable `max_arg_bytes`, `max_return_bytes`, `max_total_bytes`, `binary_threshold`
- **`MetaExtractor`** (`nfo/extractors.py`) — intelligent type detection and metadata extraction for binary payloads:
  - Image meta (PNG/JPEG/BMP): format, dimensions, size, SHA-256 prefix
  - Audio meta (WAV): channels, sample rate, bits per sample, duration
  - Binary meta: format detection via magic bytes, entropy, compression detection
  - File handle meta: name, mode, position, size (without reading contents)
  - NumPy ndarray meta (duck-typed): shape, dtype, size, min/max/mean
  - Pandas DataFrame meta (duck-typed): shape, columns, dtypes, memory, nulls
  - `register_extractor()` / `unregister_all_extractors()` for custom type support
- **`@meta_log`** (`nfo/meta_decorators.py`) — dedicated decorator for binary data pipelines; never logs raw `bytes`/`bytearray` above threshold; supports sync + async, custom `extract_fields`, per-argument extractors
- **`BinaryAwareRouter`** (`nfo/binary_router.py`) — sink that routes log entries based on payload characteristics: meta-log entries → lightweight sink, large binary data → heavy sink, normal entries → full sink
- **`@log_call(extract_meta=True)`** — opt-in metadata extraction in existing decorator; zero breaking changes; optional `meta_policy` parameter
- **`@catch(extract_meta=True)`** — same integration for `@catch` decorator
- **`configure(meta_policy=..., auto_extract_meta=True)`** — global configuration for metadata extraction
- **Environment variables**: `NFO_META_THRESHOLD` (bytes), `NFO_META_EXTRACT` (true/false)
- **`AsyncBufferedSink`** (`nfo/buffered_sink.py`) — background-thread batched writes; configurable `buffer_size`, `flush_interval`, `flush_on_error`; auto-flush on ERROR/CRITICAL; manual `flush()` and `pending` property
- **`RingBufferSink`** (`nfo/ring_buffer_sink.py`) — in-memory ring buffer (configurable capacity) that flushes context to delegate on ERROR/CRITICAL; zero disk I/O during normal operation; customizable `trigger_levels` and `include_trigger`
- **`sample_rate`** parameter on `@log_call`, `@catch`, and `@meta_log` — fraction of calls to log (0.0–1.0); errors are **always** logged regardless of sampling
- **111 new tests** across 8 test files: `test_meta.py` (20), `test_extractors.py` (30), `test_meta_decorators.py` (20), `test_binary_router.py` (9), `test_buffered_sink.py` (11), `test_ring_buffer_sink.py` (13), sampling tests in `test_decorators.py` (8)

### Changed

- Version bump to 0.3.0 (minor: new modules, zero breaking changes)
- `__init__.py`: exports `ThresholdPolicy`, `extract_meta`, `register_extractor`, `meta_log`, `BinaryAwareRouter`, `AsyncBufferedSink`, `RingBufferSink`
- `configure.py`: accepts `meta_policy` and `auto_extract_meta`; reads `NFO_META_THRESHOLD` and `NFO_META_EXTRACT` env vars
- `decorators.py`: `@log_call` and `@catch` accept `sample_rate` (sampling check deferred after function execution for zero overhead on skipped calls)
- `meta_decorators.py`: `@meta_log` accepts `sample_rate`

## [0.2.8] - 2026-02-15

### Summary

feat(docs): docs module improvements

### Docs

- docs: update README

### Build

- update pyproject.toml


## [0.2.7] - 2026-02-15

### Summary

feat(docs): code analysis engine

### Docs

- docs: update README
- docs: update TODO.md
- docs: update README
- docs: update function-reference.md
- docs: update project-analysis.md

### Other

- update project.functions.toon
- scripts: update project.sh
- update project.toon-schema.json


## [0.2.6] - 2026-02-15

### Summary

feat(docs): comprehensive project analysis with function index

### Added

- **Project function index** (`project.functions.toon`) - comprehensive analysis of 46 modules and 448 functions
- **Project metrics section** in README with detailed statistics:
  - 46 modules across core, tests, examples, and demo
  - 448 total functions with comprehensive metadata tracking  
  - 114 tests with full coverage of all sinks and decorators
  - 7 sink types: SQLite, CSV, Markdown, JSON, Prometheus, Webhook, LLM
  - Multi-language support: Python (core), Go, Rust, Bash clients
  - DevOps ready: Docker Compose, Kubernetes, gRPC, HTTP services

### Docs

- Update README with project metrics from function index analysis
- Update version reference from v0.2.3 to v0.2.6

### Analysis

- Function distribution shows strong focus on decorators, sinks, and logging infrastructure
- Test coverage indicates comprehensive validation of all major components
- Multi-language examples demonstrate broad integration capabilities
- Demo applications provide realistic load generation and monitoring scenarios

## [0.2.6] - 2026-02-14

### Summary

fix(docs): CLI interface with 3 supporting modules

### Docs

- docs: update README

### Test

- update tests/test_auto.py
- update tests/test_decorators.py

### Build

- update pyproject.toml

### Other

- update .bumpversion.cfg
- update nfo/__init__.py
- update nfo/auto.py
- update nfo/decorators.py
- update nfo/llm.py
- update nfo/logged.py
- update nfo/logger.py
- update nfo/models.py


## [0.2.5] - 2026-02-14

### Fixed

- **Oversized log payloads** — added bounded serialization for `args`, `kwargs`, `return_value`, and `kwarg_types` via `LogEntry.safe_repr` + `max_repr_length` (default: `2048`)
- **Stdlib log flooding** — `Logger._format_stdlib()` now uses truncated `LogEntry` repr helpers instead of raw `!r`
- **LLM prompt bloat** — `LLMSink` now builds prompts from truncated argument representations

### Added

- `max_repr_length` option for `@log_call`, `@catch`, `@logged`, `auto_log()`, and `auto_log_by_name()`
- Regression tests for truncation paths in decorators and auto instrumentation

## [0.2.4] - 2026-02-13

### Summary

feat(docs): deep code analysis engine with 6 supporting modules

### Docs

- docs: update README

### Other

- update img.png


# Changelog

All notable changes to `nfo` are documented here.

## [0.2.3] - 2026-02-12

### Fixed

- **`bump2version` config** — synced `.bumpversion.cfg` to track `pyproject.toml`, `VERSION`, and `nfo/__init__.py`; all three files now bump atomically
- **`env_tagger_usage.py`** — fixed `sqlite3.Row.get()` → `dict(row).get()` (Python 3.13 compat)
- **Stale pip install** — resolved nfo 0.1.17 in `site-packages` shadowing local source

### Added

- **`nfo` CLI** — universal command proxy with automatic logging:
  - `nfo run -- <cmd>` — run any command with nfo logging (args, stdout/stderr, return code, duration, language auto-detection)
  - `nfo logs [db] [--errors] [--level] [--last 24h] [--function]` — query SQLite logs with color output
  - `nfo serve [--port] [--host]` — start centralized HTTP logging service (built-in FastAPI, no external file needed)
  - `nfo version` — print version
  - Entry point registered in `pyproject.toml` (`[project.scripts]`)
- **`nfo/__main__.py`** — `python -m nfo` support
- **`nfo serve`** — inline HTTP logging service with `POST /log`, `POST /log/batch`, `GET /logs`, `GET /health`
- **gRPC server** (`examples/grpc_server.py`) — high-performance Python gRPC logging service implementing `LogCall`, `BatchLog`, `StreamLog` (bidirectional), `QueryLogs`
- **gRPC client** (`examples/grpc_client.py`) — Python gRPC client demo for all 4 RPCs
- **`[grpc]` optional dependency** — `pip install nfo[grpc]` installs `grpcio` + `grpcio-tools`
- **Root `Dockerfile`** — used by `examples/docker-compose-service.yml` for centralized logging service
- **Multi-language examples** — verified and tested: Go client, Rust client, Bash client, gRPC proto, Kubernetes manifests, Docker Compose service stack
- **`.env.example` files** — root + `examples/` with all `NFO_*` variables documented
- **`examples/http_service.py`** — standalone FastAPI centralized logging service with `.env` support
- **`examples/bash_wrapper.py`** — nfo-bash proxy for shell scripts → SQLite
- **`examples/bash_client.sh`** — zero-dependency Bash HTTP client (`nfo_log`, `nfo_run`, `nfo_query`)
- **`examples/env_config_usage.py`** — `.env` file configuration with python-dotenv
- **`examples/async_usage.py`**, **`auto_log_usage.py`**, **`configure_usage.py`**, **`env_tagger_usage.py`** — new Python examples

## [0.2.0] - 2026-02-12

### Added

- **`PrometheusSink`** — export function call metrics (duration histogram, call count, error rate) to Prometheus; auto `/metrics` endpoint; optional dep `pip install nfo[prometheus]`
- **`WebhookSink`** — HTTP POST alerts to Slack, Discord, or Microsoft Teams on ERROR; fire-and-forget with format templates; zero external dependencies (stdlib `urllib`)
- **`JSONSink`** — structured JSON Lines output for ELK/Grafana Loki/Fluentd; zero external dependencies
- **Docker Compose demo stack** — `nfo-demo` (FastAPI) + Prometheus + Grafana with pre-built dashboard
- **Grafana dashboard** — auto-provisioned: calls/s, error rate, p95 duration, histogram, top functions
- **Load generator** — `demo/load_generator.py` for populating metrics
- `configure()` now supports `json:path` and `prometheus:port` sink specs
- 27 new tests for `PrometheusSink`, `WebhookSink`, `JSONSink` (114 total)
- Optional dependency groups: `[prometheus]`, `[dashboard]`

### Changed

- Version bump to 0.2.0 (minor: new sinks, Docker Compose, DevOps integration)
- `pyproject.toml`: added `[prometheus]` and `[dashboard]` optional dependency groups
- `[dev]` group now includes `pytest-asyncio` and `prometheus_client`

## [0.1.19] - 2026-02-12

### Fixed

- **Duplicate log lines** — set `propagate=False` on stdlib logger to prevent double output
- **Re-configuration guard** — `configure()` now returns cached logger on repeated calls (use `force=True` to override)

## [0.1.18] - 2026-02-12

### Fixed

- Version sync between `__init__.py` and `pyproject.toml`

## [0.1.17] - 2026-02-12

### Fixed

- `__version__` in `__init__.py` synced with `pyproject.toml` (was out of date)

## [0.1.15] - 2026-02-12

### Added

- **Async support** — `@log_call`, `@catch`, and `@logged` now transparently handle `async def` functions via `inspect.iscoroutinefunction()`
- Async tests: 7 new tests for async `@log_call` and `@catch`

## [0.1.14] - 2026-02-11

### Added

- **`auto_log_by_name()`** — like `auto_log()` but accepts module name strings; resolves from `sys.modules`
- **`auto_log()`** — one-call module-level patching: wraps all functions in a module with `@log_call` or `@catch` without individual decorators
- `LogEntry` sinks now persist `environment`, `trace_id`, `version`, `llm_analysis` fields
- **Comparison table** with loguru, structlog, stdlib logging in README
- CHANGELOG.md, TODO.md

## [0.1.13] - 2026-02-11

### Added

- **`LLMSink`** — LLM-powered log analysis via litellm (OpenAI, Anthropic, Ollama)
- **`detect_prompt_injection()`** — regex-based prompt injection detection in function args
- **`EnvTagger`** — auto-tags logs with environment (prod/dev/ci/k8s/docker), trace_id, version
- **`DynamicRouter`** — routes logs to different sinks based on env/level/custom rules
- **`DiffTracker`** — detects output changes between function versions (A/B testing)
- `LogEntry` extended with `environment`, `trace_id`, `version`, `llm_analysis` fields
- `configure()` extended with `llm_model`, `environment`, `version`, `detect_injection` params
- `litellm` as optional dependency: `pip install nfo[llm]`

### Changed

- `pyproject.toml`: added `[llm]` and `[all]` optional dependency groups

## [0.1.12] - 2026-02-11

### Added

- **`configure()`** — one-liner project-wide logging setup with sink specs and stdlib bridge
- **`@logged`** — class decorator that auto-wraps all public methods with `@log_call`
- **`@skip`** — exclude specific methods from `@logged`
- **`_StdlibBridge`** — forwards stdlib `logging.getLogger()` records to nfo sinks
- `import nfo.setup` — zero-config auto-setup on import
- Example scripts: `basic_usage.py`, `sqlite_sink.py`, `csv_sink.py`, `markdown_sink.py`, `multi_sink.py`
- Integration modules for pactown (`nfo_config.py`) and pactown-com (`nfo_config.py`)

## [0.1.11] - 2026-02-11

### Changed

- Renamed package from `lg` to `nfo` (PyPI: `pip install nfo`)
- Updated all imports, tests, and packaging from `lg` to `nfo`

## [0.1.1] - 2026-02-11

### Added

- Initial release
- **`@log_call`** — decorator that logs function entry/exit, args, types, return value, exceptions, duration
- **`@catch`** — like `@log_call` but suppresses exceptions (returns configurable default)
- **`Logger`** — central dispatcher with multiple sinks + optional stdlib forwarding
- **`SQLiteSink`** — persist logs to SQLite database (queryable)
- **`CSVSink`** — append logs to CSV file
- **`MarkdownSink`** — write human-readable Markdown log files
- `LogEntry` dataclass with full function call metadata
- Thread-safe sinks with locks
- Zero external dependencies (stdlib only for core)

# nfo Function Reference

This document provides a comprehensive reference of all functions in the nfo project, organized by module and category.

#### `@log_call`
Automatically logs function calls with arguments, return values, exceptions, and duration.

```python
@log_call
def my_function(arg1, arg2):
    return arg1 + arg2
```

**Parameters:**
- `func` (Optional[Callable]) - Function to decorate
- `level` (str) - Log level (default: "DEBUG")
- `logger` (Optional[Logger]) - Custom logger instance
- `max_repr_length` (Optional[int]) - Truncate long representations

**Returns:** Decorated function

#### `@catch`
Like `@log_call` but suppresses exceptions and returns a default value.

```python
@catch(default=None)
def risky_function():
    return 1 / 0  # Returns None instead of raising
```

**Parameters:**
- `func` (Optional[Callable]) - Function to decorate
- `default` (Any) - Value to return on exception (default: None)
- `level` (str) - Log level (default: "ERROR")
- `logger` (Optional[Logger]) - Custom logger instance
- `max_repr_length` (Optional[int]) - Truncate long representations

**Returns:** Decorated function

#### `@logged`
Class decorator that automatically wraps all public methods with `@log_call`.

```python
@logged
class MyService:
    def method1(self): pass  # Will be logged
    def _private(self): pass  # Won't be logged
```

**Parameters:**
- `cls` (Optional[Type]) - Class to decorate
- `level` (str) - Log level for all methods
- `logger` (Optional[Logger]) - Custom logger instance
- `max_repr_length` (Optional[int]) - Truncate long representations

**Returns:** Decorated class

#### `@skip`
Mark a public method to be excluded from `@logged` auto-wrapping.

```python
@logged
class MyService:
    @skip
    def health_check(self): pass  # Excluded from logging
```

#### `auto_log(*modules, **kwargs)`
Automatically wrap all functions in specified modules with logging decorators.

```python
import mymodule
auto_log(mymodule, level="INFO", catch_exceptions=True)
```

**Parameters:**
- `*modules` - Module objects to instrument
- `level` (str) - Log level for all functions
- `catch_exceptions` (bool) - Use @catch instead of @log_call
- `default` (Any) - Default value for @catch
- `include_private` (bool) - Also wrap private functions
- `max_repr_length` (Optional[int]) - Truncate long representations

**Returns:** Number of functions patched

#### `auto_log_by_name(*module_names, **kwargs)`
Like `auto_log()` but accepts module name strings.

```python
auto_log_by_name("myapp.api", "myapp.core", level="INFO")
```

**Parameters:**
- `*module_names` - Module names to instrument
- Same kwargs as `auto_log()`

**Returns:** Number of functions patched

#### `configure(**kwargs)`
One-liner project setup with automatic environment variable support.

```python
configure(
    sinks=["sqlite:logs.db", "csv:logs.csv"],
    level="INFO",
    modules=["myapp.api", "myapp.core"]
)
```

**Parameters:**
- `name` (str) - Logger name (default: "nfo")
- `level` (str) - Log level (default: "DEBUG")
- `sinks` (List[Union[str, Sink]]) - Sink specifications or instances
- `modules` (List[str]) - Stdlib modules to bridge
- `propagate_stdlib` (bool) - Forward to stdlib loggers
- `environment` (str) - Environment tag
- `version` (str) - Application version
- `llm_model` (str) - LLM model for analysis
- `detect_injection` (bool) - Enable prompt injection detection
- `force` (bool) - Re-configure even if already configured

**Returns:** Configured Logger instance

#### `SQLiteSink(db_path, table)`
Persist logs to SQLite database for querying.

```python
sink = SQLiteSink("logs.db", table="function_calls")
```

**Parameters:**
- `db_path` (Any) - Database file path
- `table` (str) - Table name (default: "logs")

#### `CSVSink(file_path)`
Append logs to CSV file.

```python
sink = CSVSink("logs.csv")
```

**Parameters:**
- `file_path` (Any) - CSV file path

#### `MarkdownSink(file_path)`
Write human-readable Markdown logs.

```python
sink = MarkdownSink("logs.md")
```

**Parameters:**
- `file_path` (Any) - Markdown file path

#### `JSONSink(file_path, pretty)`
Write structured JSON Lines output.

```python
sink = JSONSink("logs.jsonl", pretty=False)
```

**Parameters:**
- `file_path` (Any) - JSON file path
- `pretty` (bool) - Pretty-print JSON (default: False)

#### PrometheusSink (`nfo.prometheus`)
Export function call metrics to Prometheus.

```python
sink = PrometheusSink(
    delegate=SQLiteSink("logs.db"),
    port=9090
)
```

**Parameters:**
- `delegate` (Optional[Sink]) - Downstream sink
- `port` (int) - Metrics server port
- `prefix` (str) - Metric name prefix

**Methods:**
- `get_metrics()` - Return current metrics in Prometheus format

#### WebhookSink (`nfo.webhook`)
Send HTTP alerts to Slack, Discord, or Teams.

```python
sink = WebhookSink(
    url="https://hooks.slack.com/...",
    levels=["ERROR"],
    format="slack"
)
```

**Parameters:**
- `url` (str) - Webhook URL
- `delegate` (Optional[Sink]) - Downstream sink
- `levels` (List[str]) - Log levels to alert on
- `format` (str) - Payload format: "slack", "discord", "teams", "raw"

#### LLMSink (`nfo.llm`)
AI-powered log analysis via litellm.

```python
sink = LLMSink(
    model="gpt-4o-mini",
    delegate=SQLiteSink("logs.db"),
    detect_injection=True
)
```

**Parameters:**
- `model` (str) - LLM model name
- `delegate` (Optional[Sink]) - Downstream sink
- `detect_injection` (bool) - Scan for prompt injection
- `analyze_levels` (List[str]) - Levels to analyze (default: ["ERROR"])

#### EnvTagger
Auto-tag logs with environment, trace ID, and version.

```python
sink = EnvTagger(
    SQLiteSink("logs.db"),
    environment="prod",
    trace_id="abc123"
)
```

**Parameters:**
- `delegate` (Sink) - Downstream sink
- `environment` (Optional[str]) - Environment tag
- `trace_id` (Optional[str]) - Trace ID
- `version` (Optional[str]) - Application version

#### DynamicRouter
Route logs to different sinks based on rules.

```python
router = DynamicRouter([
    (lambda e: e.level == "ERROR", SQLiteSink("errors.db")),
    (lambda e: e.environment == "prod", PrometheusSink())
])
```

**Parameters:**
- `rules` (List[tuple]) - (predicate, sink) pairs
- `default` (Optional[Sink]) - Default sink

#### DiffTracker
Detect when function output changes between versions.

```python
sink = DiffTracker(SQLiteSink("logs.db"))
```

**Parameters:**
- `delegate` (Sink) - Downstream sink

#### `detect_prompt_injection(text)`
Scan text for common prompt injection patterns.

```python
result = detect_prompt_injection("ignore previous instructions")
```

**Parameters:**
- `text` (str) - Text to scan

**Returns:** Optional[str] - Injection type if detected

#### `scan_entry_for_injection(entry)`
Scan a LogEntry's arguments for prompt injection.

```python
injection = scan_entry_for_injection(log_entry)
```

**Parameters:**
- `entry` (LogEntry) - Log entry to scan

**Returns:** Optional[str] - Injection type if detected

#### `generate_trace_id()`
Generate a new trace ID for distributed tracing.

```python
trace_id = generate_trace_id()
```

**Returns:** str - UUID-based trace ID

#### `safe_repr(value, max_length)`
Safe string representation with truncation.

```python
repr_str = safe_repr(large_object, max_length=512)
```

**Parameters:**
- `value` (Any) - Value to represent
- `max_length` (Optional[int]) - Maximum length

**Returns:** str - Safe representation

#### `nfo run -- <command>`
Run any command with automatic logging.

```bash
nfo run -- python script.py
nfo run -- bash deploy.sh prod
```

#### `nfo logs [options]`
Query logs from SQLite database.

```bash
nfo logs --errors --last 24h
nfo logs --function deploy -n 50
```

#### `nfo serve [--port]`
Start centralized HTTP logging service.

```bash
nfo serve --port 8080
```

#### `nfo version`
Print nfo version.

```bash
nfo version
```

### LogEntry (`nfo.models`)

Core data structure representing a function call log.

**Fields:**
- `timestamp` (datetime) - UTC timestamp
- `level` (str) - Log level (DEBUG/ERROR)
- `function_name` (str) - Qualified function name
- `module` (str) - Python module
- `args` (tuple) - Positional arguments
- `kwargs` (dict) - Keyword arguments
- `arg_types` (tuple) - Argument type names
- `kwarg_types` (dict) - Keyword argument type names
- `return_value` (Any) - Function return value
- `return_type` (str) - Return value type
- `exception` (Optional[str]) - Exception message
- `exception_type` (Optional[str]) - Exception class name
- `traceback` (Optional[str]) - Full traceback
- `duration_ms` (float) - Execution time in milliseconds
- `environment` (Optional[str]) - Environment tag
- `trace_id` (Optional[str]) - Trace ID
- `version` (Optional[str]) - Application version
- `llm_analysis` (Optional[str]) - LLM analysis result
- `extra` (dict) - Additional metadata

**Methods:**
- `now()` - Create timestamp
- `args_repr()` - Get truncated args representation
- `kwargs_repr()` - Get truncated kwargs representation
- `return_value_repr()` - Get truncated return value representation
- `as_dict()` - Convert to flat dictionary

### Logger (`nfo.logger`)

Central dispatcher for log entries.

**Methods:**
- `add_sink(sink)` - Register a sink
- `remove_sink(sink)` - Remove a sink
- `emit(entry)` - Send entry to all sinks
- `close()` - Close all sinks

## Sink Interface

All sinks implement the same interface:

```python
class Sink:
    def write(self, entry: LogEntry) -> None:
        """Write a log entry."""
        pass
    
    def close(self) -> None:
        """Close the sink and release resources."""
        pass
```

## Environment Variables

nfo automatically reads these environment variables:

- `NFO_LEVEL` - Default log level
- `NFO_SINKS` - Comma-separated sink specifications
- `NFO_ENV` - Environment tag
- `NFO_VERSION` - Application version
- `NFO_LLM_MODEL` - LLM model name
- `OPENAI_API_KEY` - OpenAI API key (for LLM features)
- `NFO_WEBHOOK_URL` - Webhook URL for alerts
- `NFO_PROMETHEUS_PORT` - Prometheus metrics port
- `NFO_LOG_DIR` - Directory for log files
- `NFO_PORT` - HTTP service port

## Sink Specifications

String format for `configure()` and CLI:

```
sqlite:path/to/db.db
csv:path/to/file.csv
md:path/to/file.md
json:path/to/file.jsonl
prometheus:9090
```

### Common Exceptions

- **ImportError** - Optional dependencies not installed
- **sqlite3.Error** - Database connection issues
- **FileNotFoundError** - Invalid file paths
- **ConnectionError** - Webhook/network issues
- **ValueError** - Invalid configuration

### Best Practices

1. Always wrap risky operations with `@catch`
2. Use appropriate log levels (DEBUG for success, ERROR for failures)
3. Configure multiple sinks for redundancy
4. Set `max_repr_length` for functions with large arguments
5. Use environment variables for deployment-specific configuration

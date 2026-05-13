# Click Integration Examples

Demonstrates nfo's Click CLI integration with automatic command logging
and 5 terminal output formats.

## Prerequisites

```bash
pip install nfo click rich  # rich is optional, for markdown/table formats
```

# Default color format
python demo_basic.py greet World

# Markdown rendering (requires rich)
python demo_basic.py greet World --nfo-format markdown

# TOON compact + SQLite persistence
python demo_basic.py greet World --nfo-format toon --nfo-sink sqlite:demo.db

# Table format
python demo_basic.py process --count 5 --nfo-format table

# Error logging
python demo_basic.py fail --nfo-format color
```

### `demo_formats.py` — All 5 formats side by side

```bash
python demo_formats.py
```

Output shows: ascii, color, markdown, toon, table — for both success and error cases.

# Terminal markdown + SQLite logging via configure()
python demo_configure.py deploy prod --force
python demo_configure.py migrate /tmp/test.db

# Check persisted logs
python -m nfo query demo_cli.db --last 1h
```

## Terminal Output Formats

| Format     | Description                          | Requires |
|------------|--------------------------------------|----------|
| `ascii`    | Classic single-line                  | —        |
| `color`    | ANSI colored (default)               | —        |
| `markdown` | Rich Markdown rendering              | `rich`   |
| `toon`     | Compact machine+human readable       | —        |
| `table`    | Tabular via rich.table               | `rich`   |

## Environment Variables

- `NFO_SINK` — default sink spec (e.g. `sqlite:logs.db`)
- `NFO_FORMAT` — default terminal format (e.g. `toon`)
- `NFO_LEVEL` — minimum log level (e.g. `INFO`)

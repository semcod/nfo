# HTTP Service

Centralized HTTP logging service (FastAPI) — accepts log entries from any language via REST API.

## What it shows

- **`POST /log`** — log a single entry (from Bash, Go, Rust, Node.js, etc.)
- **`POST /log/batch`** — log multiple entries in one request
- **`GET /logs`** — query stored logs with filters (level, language, limit)
- **`GET /health`** — health check endpoint
- **`.env` support** — loads configuration from `.env` via `python-dotenv`

## Run

```bash
pip install nfo fastapi uvicorn
python examples/http-service/main.py
```

# Log a single entry
curl -X POST http://localhost:8080/log \
  -H "Content-Type: application/json" \
  -d '{"cmd":"deploy","args":["prod"],"language":"bash"}'

# Batch log
curl -X POST http://localhost:8080/log/batch \
  -H "Content-Type: application/json" \
  -d '{"entries":[{"cmd":"build","args":["v1"],"language":"go"}]}'

# Query logs
curl http://localhost:8080/logs
curl http://localhost:8080/logs?level=ERROR&limit=10
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NFO_LOG_DIR` | `./logs` | Directory for SQLite/CSV/JSONL files |
| `NFO_HOST` | `0.0.0.0` | Bind host |
| `NFO_PORT` | `8080` | Bind port |

## Architecture

```
Any language ──HTTP POST──▶ nfo-service ──▶ SQLite + CSV + JSONL
  Bash (curl)                  FastAPI
  Go (net/http)                  │
  Rust (reqwest)                 ▼
  Node (fetch)              GET /logs → query
```

# Bash Client

Zero-dependency Bash HTTP client for the nfo centralized logging service — just `curl`.

## What it shows

- **`nfo_log`** — fire-and-forget log entry via HTTP POST
- **`nfo_run`** — run a command, capture output/duration/return code, and log it
- **`nfo_query`** — query recent logs from the service

## Prerequisites

Start the HTTP service first:

```bash
python examples/http-service/main.py
```

# Source as library:
source examples/bash-client/main.sh
nfo_log "deploy" prod
nfo_run ./deploy.sh prod
nfo_query

# Or run directly:
bash examples/bash-client/main.sh
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NFO_URL` | `http://localhost:8080` | nfo-service URL |
| `NFO_ENV` | `prod` | Environment tag |

## Key code

```bash
NFO_URL="${NFO_URL:-http://localhost:8080}"

nfo_log() {
    local cmd="$1"; shift
    curl -s -X POST "$NFO_URL/log" \
        -H "Content-Type: application/json" \
        -d "{\"cmd\":\"$cmd\",\"args\":[\"$*\"],\"language\":\"bash\"}" \
        >/dev/null 2>&1 &
}
```

# Docker Compose

Multi-service Docker Compose stack with nfo HTTP + gRPC services and multi-language apps.

## What it shows

- **`nfo-logger`** — centralized HTTP logging service (FastAPI)
- **`nfo-grpc`** — high-performance gRPC logging service
- **`app-python`** — Python app using nfo directly
- **`app-bash`** — Bash app sending logs via curl
- **`app-generic`** — Multi-language batch logging demo
- **`env_file`** support — all services load `.env.example`

# Copy and adjust environment
cp examples/.env.example examples/.env
```

## Run

```bash
docker compose -f examples/docker-compose/docker-compose.yml up --build
```

# Send log entry
curl -X POST http://localhost:8080/log \
  -H "Content-Type: application/json" \
  -d '{"cmd":"deploy","args":["prod"],"language":"bash"}'

# Query logs
curl http://localhost:8080/logs
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `nfo-logger` | 8080 | HTTP logging service |
| `nfo-grpc` | 50051 | gRPC logging service |
| `app-python` | — | Python app demo |
| `app-bash` | — | Bash client demo |
| `app-generic` | — | Multi-language batch demo |

## Environment

All services inherit from `env_file: .env.example`. Override specific values via `environment:` in the compose file.

```yaml
services:
  my-app:
    env_file:
      - .env.example
    environment:
      - NFO_ENV=docker
```

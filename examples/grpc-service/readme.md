# gRPC Service

High-performance gRPC logging server and client — alternative to the HTTP service for latency-sensitive environments.

## What it shows

- **`server.py`** — Python gRPC server implementing all 4 RPCs:
  - `LogCall` — log a single entry
  - `BatchLog` — log multiple entries in one round-trip
  - `StreamLog` — bidirectional streaming for high-throughput logging
  - `QueryLogs` — query stored logs with filters
- **`client.py`** — Python gRPC client demo exercising all RPCs
- **`nfo.proto`** — service definition (generate clients for Go, Rust, Java, C++, etc.)

## Setup

```bash
pip install nfo[grpc]
## Regenerate stubs (if proto changes)

```bash
cd examples/grpc-service
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. nfo.proto
```

# Start server
python examples/grpc-service/server.py
python examples/grpc-service/server.py --port 50052 --db custom.db

# Run client demo
python examples/grpc-service/client.py
python examples/grpc-service/client.py --host localhost:50052
```

## Files

| File | Description |
|------|-------------|
| `server.py` | gRPC server with nfo SQLite backend |
| `client.py` | Python client demo (all 4 RPCs) |
| `nfo.proto` | Protobuf service definition |
| `nfo_pb2.py` | Generated message classes |
| `nfo_pb2_grpc.py` | Generated service stubs |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `NFO_GRPC_PORT` | `50051` | gRPC server port |
| `NFO_LOG_DIR` | `./logs` | Log directory |
| `NFO_DB` | `logs/nfo_grpc.db` | SQLite database path |

# Go
protoc --go_out=. --go-grpc_out=. nfo.proto

# C++ / Java / etc.
protoc --cpp_out=. --grpc_out=. --plugin=protoc-gen-grpc=grpc_cpp_plugin nfo.proto
```

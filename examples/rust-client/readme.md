# Rust Client

Rust HTTP client for the nfo centralized logging service using `reqwest`.

## What it shows

- **`nfo_log()`** — async log entry via HTTP POST
- **`nfo_log_batch()`** — batch multiple entries
- **`nfo_query()`** — query logs from the service
- Configurable via `NFO_URL` environment variable

## Prerequisites

Start the HTTP service first:

```bash
python examples/http-service/main.py
```

## Run

```bash
cd examples/rust-client
## Key code

```rust
#[derive(Serialize)]
struct LogEntry<'a> {
    cmd: &'a str,
    args: Vec<&'a str>,
    language: &'a str,
}

pub async fn nfo_log(cmd: &str, args: Vec<&str>) {
    let client = Client::new();
    let entry = LogEntry { cmd, args, language: "rust" };
    let _ = client.post(&format!("{}/log", nfo_url()))
                  .json(&entry)
                  .send()
                  .await;
}
```

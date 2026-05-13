# Kubernetes

Kubernetes deployment manifests for the nfo centralized logging service.

## What it shows

- **Deployment** — 3 replicas of nfo-logger with resource limits
- **Service** — ClusterIP service on port 8080
- **PersistentVolumeClaim** — 10Gi volume for SQLite/CSV/JSONL logs
- **ConfigMap-ready** — environment variables via `env:` fields

## Deploy

```bash
kubectl apply -f examples/kubernetes/nfo-deployment.yaml
```

## Verify

```bash
kubectl get pods -l app=nfo-logger
kubectl get svc nfo-logger
kubectl logs -l app=nfo-logger --tail=20
```

# Port-forward to local
kubectl port-forward svc/nfo-logger 8080:8080

# Send log entry
curl -X POST http://localhost:8080/log \
  -H "Content-Type: application/json" \
  -d '{"cmd":"deploy","args":["prod"],"language":"bash"}'
```

## Configuration

Set via environment variables in the Deployment spec:

```yaml
env:
  - name: NFO_SINKS
    value: "sqlite:/logs/nfo.db,prometheus"
  - name: NFO_ENV
    value: "k8s"
```

## Sidecar pattern

Inject nfo as a sidecar in any pod:

```yaml
containers:
  - name: app
    image: my-app
  - name: nfo-proxy
    image: yourorg/nfo-logger:latest
    ports:
      - containerPort: 8080
```

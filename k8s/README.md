# Formula SE — Kubernetes deployment

Production-ready manifests (Kustomize) for the Formula SE stack: API, background
worker, web/SPA, and an optional in-cluster Postgres.

## Layout

| File | What |
|---|---|
| `namespace.yaml` | Namespace with `restricted` Pod Security enforcement |
| `configmap.yaml` | Non-secret config (env, B2 bucket/region, feature flags) |
| `secret.example.yaml` | Template for secrets — copy to `secret.yaml` (gitignored) |
| `postgres.yaml` | Postgres StatefulSet + headless Service (optional) |
| `api.yaml` | API Deployment + Service + HPA + PDB (migrations run as an init container) |
| `worker.yaml` | Worker Deployment (heartbeat-based liveness) |
| `web.yaml` | Caddy/SPA Deployment + Service + PDB |
| `ingress.yaml` | Ingress (TLS via cert-manager, large upload body size) |
| `networkpolicy.yaml` | Default-deny ingress + least-privilege allows |
| `kustomization.yaml` | Ties it together; pins image tags centrally |

## Production readiness built in

- **Migrations**: `alembic upgrade head` runs as an init container on API and
  worker. Concurrency-safe — the Alembic env takes a Postgres advisory lock, so
  many replicas serialize and no-op once at head. Pods never serve before the
  schema exists.
- **Non-root & hardened**: every workload runs `runAsNonRoot` (uid 1000), drops
  all capabilities, `allowPrivilegeEscalation: false`, `RuntimeDefault` seccomp,
  and a read-only root filesystem (writable `emptyDir` for `/tmp`). Namespace
  enforces the `restricted` Pod Security Standard.
- **Health**: API/web use HTTP `startup`/`readiness`/`liveness` probes; the
  worker writes a heartbeat file each loop and the liveness probe checks its age.
- **Availability**: 2 API + 2 web replicas, rolling updates with
  `maxUnavailable: 0`, pod anti-affinity across nodes, PodDisruptionBudgets, and
  a CPU HorizontalPodAutoscaler on the API (2–6).
- **Resources**: requests/limits on every container (bump the worker's memory
  limit for very large world saves).
- **Secrets**: kept out of git (`secret.yaml` is gitignored); use Sealed
  Secrets / External Secrets in real clusters.
- **Network**: default-deny ingress; only web←ingress, api←web, postgres←app.

## Prerequisites

- A cluster with an **ingress controller** (`ingress-nginx` assumed) and
  **cert-manager** (a `letsencrypt-prod` ClusterIssuer) for the Ingress.
- **metrics-server** for the API HPA.
- A container registry hosting the two images.

## 1. Build & push images

```bash
# from the repo root
docker build -t ghcr.io/milkshak3s/formula-se-backend:0.1.0 ./backend
docker build -t ghcr.io/milkshak3s/formula-se-web:0.1.0 ./frontend
docker push ghcr.io/milkshak3s/formula-se-backend:0.1.0
docker push ghcr.io/milkshak3s/formula-se-web:0.1.0
```

Update the tags in `kustomization.yaml` (`images:`) to match.

## 2. Configure

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
# edit k8s/secret.yaml — DB password (must match POSTGRES_PASSWORD), B2 keys,
# bootstrap admin, invite code
# edit k8s/configmap.yaml — B2 endpoint/region/bucket
# edit k8s/ingress.yaml — your host + TLS issuer
```

Using a **managed database**? Delete the `postgres.yaml` line from
`kustomization.yaml` and point `DATABASE_URL` at your instance.

Not using B2 yet? The app falls back to local disk, but that's per-pod and
ephemeral in Kubernetes — configure B2 for any real deployment.

## 3. Deploy

```bash
kubectl apply -k k8s/

# watch it come up
kubectl -n formula-se get pods -w
```

The API/worker pods stay in `Init` until migrations finish, then become Ready.
The bootstrap admin is created on first start from the Secret.

## 4. Verify

```bash
kubectl -n formula-se get deploy,sts,hpa,ingress
kubectl -n formula-se logs deploy/formula-se-api
curl -sk https://formula-se.example.com/api/health
```

## Upgrades

Build a new image tag, bump it in `kustomization.yaml`, and `kubectl apply -k`
again. New pods run migrations via their init container before the rollout
proceeds; the advisory lock keeps concurrent rollouts safe.

## Validate locally

```bash
kubectl kustomize k8s/ | kubectl apply --dry-run=client -f -
```

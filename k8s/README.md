# Formula SE — Kubernetes deployment

Production-ready manifests (Kustomize) for the Formula SE stack: API, background
worker, web/SPA, and an optional in-cluster Postgres.

## Layout

Standard Kustomize `base` + `overlays` structure:

```
k8s/
├── base/                     # portable manifests (placeholder image/host)
│   ├── namespace.yaml        # Namespace with `restricted` Pod Security
│   ├── configmap.yaml        # non-secret config (env, B2 bucket/region, flags)
│   ├── secret.example.yaml   # template → copy to base/secret.yaml (gitignored)
│   ├── postgres-cluster.yaml # CloudNativePG `Cluster` (HA Postgres, CNCF operator)
│   ├── api.yaml              # API Deployment + Service + HPA + PDB (init-container migrations)
│   ├── worker.yaml           # Worker Deployment (heartbeat liveness)
│   ├── web.yaml              # Caddy/SPA Deployment + Service + PDB
│   ├── ingress.yaml          # Ingress (TLS via cert-manager, large upload body)
│   ├── networkpolicy.yaml    # default-deny ingress on app tiers + allows
│   └── kustomization.yaml
└── overlays/
    └── prod/                 # cluster-specific: real images, host, storage class
        └── kustomization.yaml
```

The **`prod` overlay** is the concrete deployment: it points the images at the
real registry, patches the ingress host to `fse.mlk.sh` + its TLS secret, and
sets the CloudNativePG storage class. Add sibling overlays for other clusters.

## Production readiness built in

- **Database**: PostgreSQL is run by the **CloudNativePG** operator (CNCF) as a
  3-instance HA `Cluster` with automated failover and rolling minor upgrades. The
  operator generates the app credentials in a `formula-se-db-app` secret; the app
  and migrations consume its ready-made `uri` (no DB password in our own secret).
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
- **Network**: default-deny ingress on the app tiers; only web←ingress and
  api←web are allowed. DB pod networking is left to the CloudNativePG operator.

## Prerequisites

- The **CloudNativePG operator** installed cluster-wide (provides the
  `postgresql.cnpg.io` CRDs). See <https://cloudnative-pg.io>.
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

Point the overlay's `images:` at your registry/tags (`overlays/prod/kustomization.yaml`).

## 2. Configure

```bash
cp k8s/base/secret.example.yaml k8s/base/secret.yaml
# edit k8s/base/secret.yaml — B2 keys, bootstrap admin, invite code
#   (no DB password: CloudNativePG generates the formula-se-db-app secret)
# edit k8s/base/configmap.yaml — B2 endpoint/region/bucket
# edit k8s/base/postgres-cluster.yaml — instances, storage size
# edit k8s/overlays/prod/kustomization.yaml — images, ingress host, storageClass
```

Using a **managed/external database** instead of CloudNativePG? Remove
`postgres-cluster.yaml` from `base/kustomization.yaml` and give the app a
`DATABASE_URL` — e.g. add it to `secret.yaml` and reference it via `envFrom`, or
change the `DATABASE_URL` `secretKeyRef` in `base/api.yaml`/`base/worker.yaml` to
point at your own secret. A bare `postgresql://…` URL is fine; the app rewrites
it to the psycopg3 driver automatically.

Not using B2 yet? The app falls back to local disk, but that's per-pod and
ephemeral in Kubernetes (the API and worker pods wouldn't share files) —
configure B2 for any real deployment.

## 3. Deploy

```bash
kubectl apply -k k8s/overlays/prod

# watch it come up
kubectl -n formula-se get pods -w
```

The CloudNativePG `Cluster` bootstraps first; once its `formula-se-db-app`
secret exists and the DB is reachable, the API/worker init containers run
migrations, then the pods become Ready. The bootstrap admin is created on first
start from the Secret.

## 4. Verify

```bash
kubectl -n formula-se get cluster            # CloudNativePG cluster health
kubectl -n formula-se get deploy,hpa,ingress
kubectl -n formula-se logs deploy/formula-se-api
curl -s https://fse.mlk.sh/api/health
```

## Upgrades

Build a new image tag, bump it in `overlays/prod/kustomization.yaml`, and
`kubectl apply -k k8s/overlays/prod` again. New pods run migrations via their
init container before the rollout proceeds; the advisory lock keeps concurrent
rollouts safe.

## Validate locally

```bash
kubectl kustomize k8s/overlays/prod | kubectl apply --dry-run=client -f -
```

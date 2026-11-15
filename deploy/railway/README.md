# Deploying on Railway

Status: NOT YET DEPLOYED. Every step below must be confirmed live and recorded in docs/REALITY_SPIKES.md.

## 1. Bucket
Railway project → New → Bucket. Note its endpoint, region, bucket name, access key id and secret.
HydraDB needs S3 conditional writes; a local volume fails after the first restart (spike S12).

## 2. HydraDB service
New → Docker image → `ghcr.io/hydra-db/hydradb@sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880`
(the digest `latest` resolved to on 2026-11-14, recorded in REALITY_SPIKES S15; confirm it is what the service runs).
Attach a volume at `/data` (cache only; durable data lives in the bucket).
Variables:
```
CLOUD_PROVIDER=aws
AWS_BUCKET_NAME=<bucket>
AWS_DEFAULT_REGION=<region>
AWS_ENDPOINT=<bucket endpoint, https://...>
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
GRAPH_NAMESPACE=default
GRAPH_ID=default
GRAPH_CELL_ID=cell-0
GRAPH_CELLS=cell-0
GRAPH_NODE_ID=node-0
GRAPH_BOLT_NODE_ADDRESSES=node-0=hydradb.railway.internal:7687
GRAPH_ADVERTISED_BOLT_ADDR=hydradb.railway.internal:7687
GRAPH_DATA_CACHE_DIR=/data/cache
GRAPH_AUTH_TOKEN_FILE=/data/auth-token
GRAPH_ALLOW_PLAINTEXT=true
GRAPH_USAGE_REPORT_ENABLED=false
RUST_MIN_STACK=33554432
```
The token file must exist before start, and the token cannot be passed as an environment variable (S26). Set the
service's start command to:
```sh
sh -c 'printf "%s" "$HYDRA_TOKEN" > /data/auth-token && exec /usr/local/bin/graph-node'
```
with `HYDRA_TOKEN` as a service variable (32 bytes or more). Verified against the pinned image on 2026-11-15: it
writes the file and the node starts, so the image is still the unmodified one and there is no pre-deploy step. Keep HydraDB on the private network only
(no public domain). The API reaches it at `http://hydradb.railway.internal:8443`.
Plaintext is acceptable only because traffic stays on Railway's private network.

## 3. API service
New → GitHub repo → Dockerfile path `deploy/railway/api.Dockerfile`. Public domain on. Variables from `.env.example`
with `TRAILMEND_HYDRA_URL=http://hydradb.railway.internal:8443`. Check `GET /v1/ready` returns `graph_writable: true`.

The service listens on **0.0.0.0:8000**, which is what the working deployment used; `TRAILMEND_PORT` overrides it
and Railway's own `PORT` is deliberately ignored. The first redeploy of the product API bound `${PORT:-8000}`
instead and the public domain answered `502 Application failed to respond` on every route, including `/healthz`,
while the same image started and served happily in a 512 MB container locally — so if Railway ever needs another
port, set `TRAILMEND_PORT` to the port the domain targets rather than `PORT`.

The image was built and run on 2026-11-15: it answers `/healthz` 200 with `PORT` set to something else, serves the
`evidence/*.json` files it now copies in (without that copy `/v1/evidence/...` and the site's curve would have been
empty on the deployment), and with an unreachable graph `/v1/ready` answers `graph_unavailable` rather than a fake
success.

## 3b. Load the demo graph
HydraDB has no public domain, so the loader cannot reach it from a laptop. Run it inside the API service, which
already carries `src` and `config`:
```sh
railway ssh --service api -- uv run --no-dev python -m trailmend.eval.load_evidence 1
```
Then `/v1/ask` has a graph to search. The live demo graph is the one the site writes to; measured runs are separate.

## 4. Web (Vercel)
`apps/web`, env `TRAILMEND_API=https://<api>.up.railway.app`. All data fetched in server components (BFF);
the browser never calls the API directly.

Once `vercel login` has been run (flags checked against Vercel CLI 65.16.0; `--dry` and everything else refuse
without credentials):
```sh
vercel --cwd apps/web --project trailmend --create-if-missing --yes \
  --env TRAILMEND_API=https://<api>.up.railway.app \
  --build-env TRAILMEND_API=https://<api>.up.railway.app --prod
```
Then open the URL in a fresh browser, check it at 390px, and confirm the API url appears in no file under
`.next/static` (A2's acceptance; it does not locally).

## CLI, once `railway login` has been run

Flags checked against `railway` 5.74.0 on this machine. Nothing here prints a credential.

```sh
railway whoami                                   # must not say Unauthorized
railway init --name trailmend
railway bucket create trailmend --region iad --json
railway bucket info --bucket trailmend --json    # endpoint, region, bucket name
railway bucket credentials --bucket trailmend --json   # access key id and secret; keep out of the terminal history
railway add --service hydradb \
  --image 'ghcr.io/hydra-db/hydradb@sha256:ab71d651fefee13ebb23eb56d72316065bdca563ff7587442e07be663f2bf880' \
  --variables 'CLOUD_PROVIDER=aws' --variables 'AWS_BUCKET_NAME=...'   # and the rest of the list above
railway add --service api --repo <owner>/<repo> --branch main
railway variable --service api --set 'TRAILMEND_HYDRA_URL=http://hydradb.railway.internal:8443'
railway domain --service api
railway service restart --service hydradb        # then check /v1/ready again, which is A1's acceptance
```

`railway add` has no flag for a start command or a Dockerfile path, so the HydraDB service's start command (above)
and the API service's `deploy/railway/api.Dockerfile` are set in the service settings, or declared in a
`railway.json` for the API service. A volume at `/data` is attached in the dashboard.

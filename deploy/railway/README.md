# Deploying on Railway

Status: NOT YET DEPLOYED. Every step below must be confirmed live and recorded in docs/REALITY_SPIKES.md.

## 1. Bucket
Railway project → New → Bucket. Note its endpoint, region, bucket name, access key id and secret.
HydraDB needs S3 conditional writes; a local volume fails after the first restart (spike S12).

## 2. HydraDB service
New → Docker image → `ghcr.io/hydra-db/hydradb:latest` (pin the digest after the first good deploy and record it).
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
The token file must exist before start: either a start command that writes `$HYDRA_TOKEN` to `/data/auth-token`
then execs `/usr/local/bin/graph-node`, or a pre-deploy step. Keep HydraDB on the private network only
(no public domain). The API reaches it at `http://hydradb.railway.internal:8443`.
Plaintext is acceptable only because traffic stays on Railway's private network.

## 3. API service
New → GitHub repo → Dockerfile path `deploy/railway/api.Dockerfile`. Public domain on. Variables from `.env.example`
with `TRAILMEND_HYDRA_URL=http://hydradb.railway.internal:8443`. Check `GET /v1/ready` returns `graph_writable: true`.

## 4. Web (Vercel)
`apps/web`, env `TRAILMEND_API=https://<api>.up.railway.app`. All data fetched in server components (BFF);
the browser never calls the API directly.

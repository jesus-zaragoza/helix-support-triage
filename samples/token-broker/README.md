# Sample Zerobus token broker

Interim authentication bridge from the architecture note in [`docs/architecture.md`](../../docs/architecture.md). Fluent Bit 5.x can refresh OAuth client-credentials tokens, but it cannot send Databricks `authorization_details`. This service is the in-cluster `oauth2.token_url`.

Logs never pass through the broker. Fluent Bit still writes OTLP gRPC to Zerobus.

```text
Fluent Bit DaemonSet  --OAuth token request-->  token-broker (2+ replicas)
        |                                              |
        | OTLP gRPC + Bearer                           | Databricks OIDC
        v                                              | + authorization_details
     Zerobus  -->  bronze table                        v
```

This is sample code for discussion and local experiments. It is not production-hardened: no TLS, no workload identity, no secrets-manager integration, and caller auth is HTTP Basic.

## What it does

1. Authenticates the Fluent Bit caller (`client_id` / `client_secret`).
2. Maps that caller to one approved table in [`policies.json`](policies.json). Callers cannot choose `authorization_details`.
3. Mints a Zerobus token with the Databricks service principal for that table.
4. Caches the token in memory and refreshes 300 seconds before expiry (`CACHE_SKEW_SECONDS`).
5. Returns a **minimal** OAuth JSON body (`access_token`, `token_type`, `expires_in`) so stock Fluent Bit’s 4 KiB OAuth response cap still works.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/oauth2/token` | OAuth client-credentials |
| `GET` | `/healthz`, `/readyz` | Probes |
| `GET` | `/metrics` | Request / cache / failure counters |

## Run locally

Reuse the primer `.env` Databricks SP, plus one broker-only secret:

```bash
cd /path/to/FluentBitTest
export $(grep -v '^#' .env | xargs)
export BROKER_CLIENT_SECRET_FLUENTBIT_IMAGING=dev-broker-secret
python3 samples/token-broker/app.py
```

Mint a token the way Fluent Bit would:

```bash
curl -sS -u fluentbit-imaging:dev-broker-secret \
  -d grant_type=client_credentials \
  http://127.0.0.1:8080/oauth2/token
```

Expected body:

```json
{"access_token":"...","token_type":"Bearer","expires_in":3600}
```

Point a local Fluent Bit output at that URL (`samples/token-broker/fluent-bit.yaml`). For laptop tests against this repo’s generator, change the input back to the JSONL tail used in the root `fluent-bit.yaml`.

## Kubernetes shape

Manifests in [`k8s/`](k8s/):

- 2 replicas, spread across zones
- ClusterIP `zerobus-token.logging.svc.cluster.local:8080`
- policies ConfigMap, secrets from External Secrets (example Secret is a placeholder)
- NetworkPolicy: ingress only from Fluent Bit, egress to DNS + HTTPS

Create the secret from a sealed/external source, then apply:

```bash
kubectl apply -f samples/token-broker/k8s/namespace.yaml
kubectl apply -f samples/token-broker/k8s/configmap.yaml
kubectl apply -f samples/token-broker/k8s/secret.example.yaml   # replace values first
kubectl apply -f samples/token-broker/k8s/deployment.yaml
kubectl apply -f samples/token-broker/k8s/service.yaml
kubectl apply -f samples/token-broker/k8s/networkpolicy.yaml
```

Give Fluent Bit `BROKER_CLIENT_SECRET_FLUENTBIT_IMAGING` and set:

```yaml
oauth2.enable: true
oauth2.token_url: http://zerobus-token.logging.svc.cluster.local:8080/oauth2/token
oauth2.auth_method: basic
oauth2.client_id: fluentbit-imaging
oauth2.client_secret: ${BROKER_CLIENT_SECRET_FLUENTBIT_IMAGING}
```

Production should terminate TLS on the Service (mesh or internal ingress) and use `https://` in `oauth2.token_url`. Fluent Bit sends client credentials in the token request.

## Adding another application

Add a caller in `policies.json` / the ConfigMap, a distinct Databricks service principal, and a distinct broker client secret. The imaging-archive Fluent Bit must not be able to mint a token for another app table (for example, eConsent).

## What to replace before production

- HTTP Basic → workload identity or `private_key_jwt`
- In-memory cache → optional shared cache; not required at this QPS
- Plain HTTP → mTLS
- Env-var SP secrets → AWS Secrets Manager / External Secrets
- `0.0.0.0/0` egress → workspace PrivateLink / Databricks OIDC CIDRs
- Stdlib server → a supported internal platform runtime

Retire the broker when Fluent Bit can send `authorization_details` natively ([PR #12520](https://github.com/fluent/fluent-bit/pull/12520)): keep the same OTEL output and point `oauth2.token_url` at Databricks.

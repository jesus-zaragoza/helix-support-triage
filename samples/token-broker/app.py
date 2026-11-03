#!/usr/bin/env python3
"""Sample Zerobus token broker.

Fluent Bit cannot send Databricks authorization_details until upstream OAuth
support lands. This service is the in-cluster OAuth token_url: Fluent Bit
authenticates to the broker; the broker mints a table-scoped Zerobus token
and returns a minimal OAuth JSON body.

This is a sample, not a production service. Put TLS, workload identity, a
real secrets manager, and rate limits in front of it before any production use.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = logging.getLogger("token-broker")

CACHE_SKEW_SECONDS = int(os.environ.get("CACHE_SKEW_SECONDS", "300"))
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080"))
POLICIES_PATH = Path(os.environ.get("POLICIES_PATH", Path(__file__).with_name("policies.json")))

_cache_lock = threading.Lock()
# table_fqn -> {"access_token", "expires_at", "token_type"}
_cache: dict[str, dict] = {}
_policies: dict[str, dict] | None = None
_metrics = {
    "token_requests_total": 0,
    "token_cache_hits_total": 0,
    "token_mint_failures_total": 0,
    "auth_failures_total": 0,
}


def load_policies() -> dict[str, dict]:
    global _policies
    if _policies is not None:
        return _policies
    data = json.loads(POLICIES_PATH.read_text())
    callers = {}
    for row in data["callers"]:
        client_id = row["client_id"]
        secret_env = row.get("broker_secret_env", f"BROKER_CLIENT_SECRET_{client_id.upper().replace('-', '_')}")
        sp_id_env = row.get("sp_client_id_env", "DATABRICKS_CLIENT_ID")
        sp_secret_env = row.get("sp_client_secret_env", "DATABRICKS_CLIENT_SECRET")
        callers[client_id] = {
            **row,
            "broker_secret": os.environ.get(secret_env, "").strip(),
            "sp_client_id": os.environ.get(sp_id_env, "").strip(),
            "sp_client_secret": os.environ.get(sp_secret_env, "").strip(),
        }
        if not callers[client_id]["broker_secret"]:
            raise SystemExit(f"Missing broker secret env {secret_env} for {client_id}")
        if not callers[client_id]["sp_client_id"] or not callers[client_id]["sp_client_secret"]:
            raise SystemExit(f"Missing Databricks SP env for {client_id}")
    _policies = callers
    return callers


def _authorization_details(catalog: str, schema: str, table_fqn: str) -> str:
    return json.dumps(
        [
            {
                "type": "unity_catalog_privileges",
                "privileges": ["USE CATALOG"],
                "object_type": "CATALOG",
                "object_full_path": catalog,
            },
            {
                "type": "unity_catalog_privileges",
                "privileges": ["USE SCHEMA"],
                "object_type": "SCHEMA",
                "object_full_path": f"{catalog}.{schema}",
            },
            {
                "type": "unity_catalog_privileges",
                "privileges": ["SELECT", "MODIFY"],
                "object_type": "TABLE",
                "object_full_path": table_fqn,
            },
        ]
    )


def mint_databricks_token(policy: dict) -> dict:
    host = policy["databricks_host"].removeprefix("https://").removeprefix("http://").rstrip("/")
    table_fqn = policy["table"]
    catalog, schema, _table = table_fqn.split(".")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "all-apis",
            "resource": f"api://databricks/workspaces/{policy['workspace_id']}/zerobusDirectWriteApi",
            "authorization_details": _authorization_details(catalog, schema, table_fqn),
        }
    ).encode()
    req = urllib.request.Request(f"https://{host}/oidc/v1/token", data=body, method="POST")
    basic = base64.b64encode(
        f"{policy['sp_client_id']}:{policy['sp_client_secret']}".encode()
    ).decode()
    req.add_header("Authorization", "Basic " + basic)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Databricks OIDC HTTP {exc.code}: {detail[:200]}") from exc
    if "access_token" not in payload:
        raise RuntimeError("Databricks OIDC response missing access_token")
    expires_in = int(payload.get("expires_in", 3600))
    return {
        "access_token": payload["access_token"],
        "token_type": "Bearer",
        "expires_in": expires_in,
        "expires_at": time.time() + expires_in,
    }


def cached_token(policy: dict) -> dict:
    table = policy["table"]
    now = time.time()
    with _cache_lock:
        hit = _cache.get(table)
        if hit and hit["expires_at"] - now > CACHE_SKEW_SECONDS:
            _metrics["token_cache_hits_total"] += 1
            remaining = int(hit["expires_at"] - now)
            return {
                "access_token": hit["access_token"],
                "token_type": "Bearer",
                "expires_in": remaining,
            }
    minted = mint_databricks_token(policy)
    with _cache_lock:
        _cache[table] = minted
    LOG.info("minted token table=%s expires_in=%s", table, minted["expires_in"])
    return {
        "access_token": minted["access_token"],
        "token_type": "Bearer",
        "expires_in": minted["expires_in"],
    }


def authenticate(handler: BaseHTTPRequestHandler) -> dict | None:
    header = handler.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:]).decode()
        client_id, client_secret = decoded.split(":", 1)
    except Exception:
        return None
    policy = load_policies().get(client_id)
    if policy is None:
        return None
    if not secrets.compare_digest(policy["broker_secret"], client_secret):
        return None
    return policy


class Handler(BaseHTTPRequestHandler):
    server_version = "zerobus-token-broker/sample"

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - " + fmt, self.address_string(), *args)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/healthz", "/readyz"):
            self._json(200, {"status": "ok"})
            return
        if self.path == "/metrics":
            lines = [f"{k} {_metrics[k]}" for k in _metrics]
            body = ("\n".join(lines) + "\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/oauth2/token":
            self._json(404, {"error": "not_found"})
            return
        _metrics["token_requests_total"] += 1
        policy = authenticate(self)
        if policy is None:
            _metrics["auth_failures_total"] += 1
            self._json(401, {"error": "invalid_client"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        form = urllib.parse.parse_qs(raw.decode(), keep_blank_values=True)
        grant = (form.get("grant_type") or ["client_credentials"])[0]
        if grant != "client_credentials":
            self._json(400, {"error": "unsupported_grant_type"})
            return
        try:
            token = cached_token(policy)
        except Exception:
            _metrics["token_mint_failures_total"] += 1
            LOG.exception("mint failed client_id=%s table=%s", policy["client_id"], policy["table"])
            self._json(502, {"error": "temporarily_unavailable"})
            return
        # Minimal body: Fluent Bit 5.x parses a 4 KiB OAuth response unless PR 12520 is present.
        self._json(200, token)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    load_policies()
    LOG.info("starting token broker on %s:%s policies=%s", LISTEN_HOST, LISTEN_PORT, POLICIES_PATH)
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()

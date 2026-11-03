#!/usr/bin/env python3
"""Mint a 1-hour Zerobus OTLP bearer token from SP client id/secret.

Fluent Bit 5.x cannot mint this token itself (oauth2client + authorization_details),
so this runs once before a load test. Tokens expire in ~3600s.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def mint_token(
    host: str,
    client_id: str,
    client_secret: str,
    workspace_id: str,
    catalog: str,
    schema: str,
    table_fqn: str,
) -> dict:
    host = host.removeprefix("https://").removeprefix("http://").rstrip("/")
    authorization_details = json.dumps(
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
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "scope": "all-apis",
            "resource": f"api://databricks/workspaces/{workspace_id}/zerobusDirectWriteApi",
            "authorization_details": authorization_details,
        }
    ).encode()
    url = f"https://{host}/oidc/v1/token"
    req = urllib.request.Request(url, data=body, method="POST")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req.add_header("Authorization", "Basic " + basic)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"Token request failed HTTP {exc.code}: {detail}") from exc
    if "access_token" not in payload:
        raise SystemExit(f"Token response missing access_token: {payload}")
    return payload


def main() -> None:
    _load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "logs" / ".zerobus_token"))
    args = parser.parse_args()

    client_id = os.environ.get("DATABRICKS_CLIENT_ID", "").strip()
    client_secret = os.environ.get("DATABRICKS_CLIENT_SECRET", "").strip()
    host = os.environ.get("DATABRICKS_HOST", "").strip()
    workspace_id = os.environ.get("WORKSPACE_ID", "").strip()
    table_fqn = os.environ.get(
        "DATABRICKS_LOGS_TABLE", "accessdemo.fluentbit.helix_otel_logs"
    ).strip()
    parts = table_fqn.split(".")
    if len(parts) != 3:
        raise SystemExit(f"DATABRICKS_LOGS_TABLE must be catalog.schema.table, got {table_fqn!r}")
    catalog, schema, _ = parts

    missing = [
        name
        for name, val in [
            ("DATABRICKS_CLIENT_ID", client_id),
            ("DATABRICKS_CLIENT_SECRET", client_secret),
            ("DATABRICKS_HOST", host),
            ("WORKSPACE_ID", workspace_id),
        ]
        if not val
    ]
    if missing:
        raise SystemExit(f"Missing required env: {', '.join(missing)}. Copy .env.example to .env.")

    payload = mint_token(
        host, client_id, client_secret, workspace_id, catalog, schema, table_fqn
    )
    token = payload["access_token"]
    expires = payload.get("expires_in", 3600)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(token + "\n")
    os.chmod(out, 0o600)
    print(f"Wrote token to {out} (expires_in={expires}s)", file=sys.stderr)
    print(token)


if __name__ == "__main__":
    main()

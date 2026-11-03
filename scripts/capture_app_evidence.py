#!/usr/bin/env python3
"""Call the deployed Helix Support Console APIs and write the responses to evidence/07_app_api.md.

Exercises every stage the app touches: Lakebase reads (synced gold tables), a Lakebase write
(triage note), and the Genie Agent through the app's own service principal.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import requests
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app", default="helix-support-console")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai"))
    args = p.parse_args()

    w = WorkspaceClient(profile=args.profile)
    app = w.apps.get(args.app)
    base = app.url.rstrip("/")
    s = requests.Session()
    s.headers.update(w.config.authenticate())

    def call(method: str, path: str, body: dict | None = None, trim=None) -> list[str]:
        r = s.request(method, base + path, json=body, timeout=300)
        r.raise_for_status()
        data = r.json()
        shown = trim(data) if trim else data
        req = f"{method} {path}" + (f"\n{json.dumps(body, indent=2)}" if body else "")
        return [f"### `{method} {path}`", "", "Request:", "", "```", req, "```", "",
                f"Response (HTTP {r.status_code}):", "", "```json", json.dumps(shown, indent=2, default=str)[:6000], "```", ""]

    lines = ["# Databricks App evidence: Helix Support Console", "",
             f"App `{app.name}` (FastAPI on Databricks Apps), compute `{app.compute_status.state.value}`, "
             f"deployment `{app.active_deployment.deployment_id if app.active_deployment else None}`. "
             "Resources: Lakebase `postgres` (CAN_CONNECT_AND_CREATE), `sql-warehouse` (CAN_USE), "
             "`genie-space` (CAN_RUN). Calls below were made with a workspace OAuth token against the live app.", ""]
    lines += call("GET", "/api/health", trim=lambda d: {**d, "lakebase": {**d["lakebase"], "db_user": "<app-sp>"}})
    lines += call("GET", "/api/clients")
    lines += call("GET", "/api/clients/fabrikam-cro", trim=lambda d: {
        "client_id": d["client_id"], "timeline_hours": len(d["timeline"]),
        "worst_hours": sorted(d["timeline"], key=lambda t: -float(t["errors"]) / max(float(t["events"]), 1))[:3],
        "sites": d["sites"][:5], "anomalies_count": len(d["anomalies"]),
        "briefs": [{k: b[k] for k in ("incident_id", "severity", "started_at", "ended_at", "client_reply") if k in b}
                   for b in d["briefs"]],
        "notes": d["notes"]})
    lines += call("POST", "/api/notes", {
        "ticket_id": "SUP-4813", "client_id": "contoso-tx", "incident_id": "contoso-tx-20261102-0910",
        "status": "resolved", "author": "support-analyst-demo",
        "note": "E-signature vendor confirmed 503 outage 09:05-09:58 UTC; circuit breaker enabled, AI draft reply sent to all 3 sites."})
    lines += call("GET", "/api/notes")
    lines += call("POST", "/api/genie",
                  {"question": "Which Fabrikam CRO services had the worst error rate between 17:00 and 19:30?"})
    out = ROOT / "evidence" / "07_app_api.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Grant the Support Console app's service principal read access to the Lakebase synced tables,
then print row counts and sample rows from Postgres (written to evidence/04_lakebase_serving.md).

Synced tables are created by the pipeline owner, so the app role needs USAGE + SELECT on the
synced Postgres schema. The app creates and owns its own `support_app` schema for triage notes.

Usage:
  python scripts/lakebase_grant_and_verify.py --app helix-support-console \
      --sync-schema dev_jesus_zaragoza_helix_support
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg2
from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "projects/helix-support/branches/production/endpoints/primary"


def table(cur, sql: str, limit: int = 10) -> list[str]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(limit)
    out = ["```sql", sql.strip(), "```", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join("" if v is None else str(v)[:120] for v in r) + " |" for r in rows]
    return out + [""]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--app", default="helix-support-console")
    p.add_argument("--sync-schema", default="dev_jesus_zaragoza_helix_support")
    p.add_argument("--database", default="databricks_postgres")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai"))
    args = p.parse_args()

    w = WorkspaceClient(profile=args.profile)
    sp = w.apps.get(args.app).service_principal_client_id
    host = w.postgres.get_endpoint(ENDPOINT).status.hosts.host
    conn = psycopg2.connect(host=host, port=5432, dbname=args.database, sslmode="require",
                            user=w.current_user.me().user_name,
                            password=w.postgres.generate_database_credential(endpoint=ENDPOINT).token)
    conn.autocommit = True
    s = args.sync_schema
    with conn.cursor() as cur:
        for stmt in (f'GRANT USAGE ON SCHEMA "{s}" TO "{sp}"',
                     f'GRANT SELECT ON ALL TABLES IN SCHEMA "{s}" TO "{sp}"',
                     f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{s}" GRANT SELECT ON TABLES TO "{sp}"'):
            cur.execute(stmt)
            print("OK", stmt.replace(sp, "<app-sp>"))

        lines = ["# Lakebase operational serving evidence", "",
                 f"Lakebase Autoscaling project `helix-support`, branch `production`, database `{args.database}`. "
                 "Gold Delta tables are synced (SNAPSHOT) into Postgres schema "
                 f"`{s}` as `lb_*`; the app writes triage notes to `support_app.triage_notes`.", "",
                 "Grants issued to the app service principal role: USAGE on the synced schema, SELECT on its tables "
                 "(plus default privileges for future syncs).", ""]
        lines += table(cur, f"""
SELECT table_schema, table_name, (xpath('/row/c/text()',
       query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text::bigint AS row_count
FROM information_schema.tables
WHERE table_schema IN ('{s}', 'support_app')
ORDER BY 1, 2""", 20)
        lines += table(cur, f"""
SELECT client_name, round(100.0 * sum(error_count) / sum(event_count), 2) AS error_rate_pct,
       sum(event_count) AS events
FROM "{s}".lb_gold_client_health GROUP BY client_name ORDER BY error_rate_pct DESC""")
        lines += table(cur, f"""
SELECT incident_id, client_name, severity, started_at, ended_at
FROM "{s}".lb_gold_incident_briefs ORDER BY severity, started_at""", 15)
        lines += table(cur, """
SELECT note_id, ticket_id, client_id, incident_id, status, author, left(note, 80) AS note, created_at
FROM support_app.triage_notes ORDER BY note_id DESC""") if _exists(cur) else []
    conn.close()
    out = ROOT / "evidence" / "04_lakebase_serving.md"
    out.write_text("\n".join(lines).replace(sp, "<app-sp>") + "\n")
    print(f"wrote {out}")


def _exists(cur) -> bool:
    cur.execute("SELECT to_regclass('support_app.triage_notes') IS NOT NULL")
    return cur.fetchone()[0]


if __name__ == "__main__":
    main()

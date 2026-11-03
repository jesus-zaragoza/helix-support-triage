"""Lakebase operational serving: SNAPSHOT-sync gold Delta tables into Postgres.

This is the Lakeflow/Lakebase serving construct. The Support Console reads
lb_gold_client_health, lb_gold_client_anomalies and lb_gold_incident_briefs from
Postgres (millisecond lookups) and writes triage notes to support_app.triage_notes
(see sql/triage_notes.sql and src/app/app.py).

Synced tables cannot be declared in DABs today (synced_database_tables is deprecated).
This module uses w.postgres.create_synced_table / pipelines.start_update instead.

Usage (notebook or CLI):
  python -c "from lakebase.sync import run; run()"
  # or: DATABRICKS_CONFIG_PROFILE=fevm-ai python src/lakebase/sync.py
"""
from __future__ import annotations

import os
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import postgres as pg

TABLES = {
    "gold_client_health": ["health_key"],
    "gold_client_anomalies": ["health_key"],
    "gold_incident_briefs": ["incident_id"],
}


def run(
    catalog: str = "accessdemo",
    schema: str = "dev_jesus_zaragoza_helix_support",
    branch: str = "projects/helix-support/branches/production",
    postgres_database: str = "databricks_postgres",
    profile: str | None = None,
    timeout_s: int = 30 * 60,
) -> dict[str, str]:
    w = WorkspaceClient(profile=profile) if profile else WorkspaceClient()
    pipelines: dict[str, str] = {}
    for src, pk in TABLES.items():
        target = f"{catalog}.{schema}.lb_{src}"
        try:
            st = w.postgres.get_synced_table(f"synced_tables/{target}")
            pipelines[target] = st.status.pipeline_id
            w.pipelines.start_update(st.status.pipeline_id)
            print(f"REFRESH {target} (pipeline {st.status.pipeline_id})")
        except Exception as exc:
            if "does not exist" not in str(exc).lower() and "not found" not in str(exc).lower():
                raise
            op = w.postgres.create_synced_table(
                synced_table=pg.SyncedTable(spec=pg.SyncedTableSyncedTableSpec(
                    source_table_full_name=f"{catalog}.{schema}.{src}",
                    primary_key_columns=pk,
                    scheduling_policy=pg.SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy.SNAPSHOT,
                    branch=branch,
                    postgres_database=postgres_database,
                    create_database_objects_if_missing=True,
                    new_pipeline_spec=pg.NewPipelineSpec(storage_catalog=catalog, storage_schema=schema),
                )),
                synced_table_id=target,
            )
            st = op.wait()
            pipelines[target] = st.status.pipeline_id
            print(f"CREATE  {target} (pipeline {st.status.pipeline_id})")

    deadline = time.time() + timeout_s
    pending = dict(pipelines)
    while pending and time.time() < deadline:
        for target, pid in list(pending.items()):
            upd = (w.pipelines.get(pid).latest_updates or [None])[0]
            state = upd.state.value if upd and upd.state else "UNKNOWN"
            if state in ("COMPLETED", "FAILED", "CANCELED"):
                print(f"{target}: {state}")
                pending.pop(target)
        if pending:
            time.sleep(20)

    for target in pipelines:
        st = w.postgres.get_synced_table(f"synced_tables/{target}")
        s = st.status
        print(f"{target}: state={s.detailed_state.value if s.detailed_state else None} "
              f"last_sync={s.last_sync_time} message={s.message}")
    if pending:
        raise TimeoutError(f"sync still running: {list(pending)}")
    return pipelines


def main() -> None:
    run(
        catalog=os.environ.get("CATALOG", "accessdemo"),
        schema=os.environ.get("SCHEMA", "dev_jesus_zaragoza_helix_support"),
        branch=os.environ.get("LAKEBASE_BRANCH", "projects/helix-support/branches/production"),
        postgres_database=os.environ.get("LAKEBASE_DATABASE_NAME", "databricks_postgres"),
        profile=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
    )


if __name__ == "__main__":
    main()

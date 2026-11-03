# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 04 · Lakebase operational serving — synced tables refresh
#
# Canonical serving code: `src/lakebase/sync.py` (`w.postgres.create_synced_table`, SNAPSHOT).
# Native write path: `sql/triage_notes.sql` and `src/app/app.py` POST /api/notes.
# This notebook is the Lakeflow Job task that calls the same SNAPSHOT sync.
#
# | Unity Catalog source | Postgres table | Primary key |
# |---|---|---|
# | `gold_client_health` | `<pg_schema>.gold_client_health` | `health_key` |
# | `gold_client_anomalies` | `<pg_schema>.gold_client_anomalies` | `health_key` |
# | `gold_incident_briefs` | `<pg_schema>.gold_incident_briefs` | `incident_id` |

# %%
import importlib.metadata as md
import subprocess
import sys

try:
    dbutils  # noqa: F821
    IN_DATABRICKS = True
except NameError:
    IN_DATABRICKS = False

if tuple(int(x) for x in md.version("databricks-sdk").split(".")[:2]) < (0, 81):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-U", "databricks-sdk>=0.81"])
    if IN_DATABRICKS:
        dbutils.library.restartPython()  # noqa: F821

# %%
import os
import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service import postgres as pg

try:
    dbutils  # noqa: F821
    IN_DATABRICKS = True
except NameError:
    IN_DATABRICKS = False


def param(name: str, default: str) -> str:
    if IN_DATABRICKS:
        dbutils.widgets.text(name, default)  # noqa: F821
        return dbutils.widgets.get(name)  # noqa: F821
    return os.environ.get(name.upper(), default)


w = WorkspaceClient() if IN_DATABRICKS else WorkspaceClient(profile=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai"))
CATALOG = param("catalog", "accessdemo")
SCHEMA = param("schema", "dev_jesus_zaragoza_helix_support")
BRANCH = param("lakebase_branch", "projects/helix-support/branches/production")
PG_DATABASE = param("lakebase_database_name", "databricks_postgres")
# Synced tables are registered in the same UC schema with an lb_ prefix; in Postgres they
# land in a schema with the UC schema's name.
TABLES = {
    "gold_client_health": ["health_key"],
    "gold_client_anomalies": ["health_key"],
    "gold_incident_briefs": ["incident_id"],
}
print(f"source={CATALOG}.{SCHEMA} branch={BRANCH} db={PG_DATABASE}")

# %%
pipelines = {}
for src, pk in TABLES.items():
    target = f"{CATALOG}.{SCHEMA}.lb_{src}"
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
                source_table_full_name=f"{CATALOG}.{SCHEMA}.{src}",
                primary_key_columns=pk,
                scheduling_policy=pg.SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy.SNAPSHOT,
                branch=BRANCH,
                postgres_database=PG_DATABASE,
                create_database_objects_if_missing=True,
                new_pipeline_spec=pg.NewPipelineSpec(storage_catalog=CATALOG, storage_schema=SCHEMA),
            )),
            synced_table_id=target,
        )
        st = op.wait()
        pipelines[target] = st.status.pipeline_id
        print(f"CREATE  {target} (pipeline {st.status.pipeline_id})")

# %%
deadline = time.time() + 30 * 60
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

# %% [markdown]
# # 01 · Unity Catalog governance — Helix support triage
#
# Applies the governance layer for the support-triage data products and prints the
# evidence as text:
#
# 1. **Functions** (`sql/governance_functions.sql`): column masks for PII (`user_email`) and
#    client-confidential study ids, and a tenant-isolation row filter. The silver table
#    definition in the Lakeflow pipeline binds them (`MASK` / `ROW FILTER`).
# 2. **Post-publish** (`sql/governance.sql`): comments, tags, grants.
# 3. **Verification**: masks/filters/tags from `information_schema`, a masked read of silver,
#    the row-filter effect, and lineage from `system.access.table_lineage`.
#
# All data is synthetic. Runs as a Lakeflow Job task on serverless, or locally through
# Databricks Connect (serverless).

# %%
import os
import re
from pathlib import Path

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


if not IN_DATABRICKS:
    from databricks.connect import DatabricksSession

    spark = DatabricksSession.builder.profile(os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai")).serverless().getOrCreate()

CATALOG = param("catalog", "accessdemo")
SCHEMA = param("schema", "dev_jesus_zaragoza_helix_support")
BRONZE = param("bronze_table", "accessdemo.fluentbit.helix_otel_logs")
PHASE = param("phase", "all")  # functions | post | all
APP_SP = param("app_sp", "")
APP_NAME = param("app_name", "")
if APP_NAME and not APP_SP:
    from databricks.sdk import WorkspaceClient

    try:
        APP_SP = WorkspaceClient().apps.get(APP_NAME).service_principal_client_id or ""
    except Exception as exc:  # app not deployed yet
        print(f"app {APP_NAME} not found ({exc.__class__.__name__}); skipping app grants")
SQL_DIR = Path.cwd().parent.parent / "sql"
print(f"catalog={CATALOG} schema={SCHEMA} bronze={BRONZE} phase={PHASE} app_sp={'set' if APP_SP else 'none'}")


def show(sql: str, limit: int = 50) -> None:
    pdf = spark.sql(sql).limit(limit).toPandas()
    print(pdf.to_string(index=False) if len(pdf) else "(no rows)")


def run_sql_file(name: str) -> None:
    text = (SQL_DIR / name).read_text()
    text = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
    subs = {"catalog": CATALOG, "schema": SCHEMA, "bronze_table": BRONZE, "app_sp": APP_SP}
    for stmt in [s.strip() for s in re.split(r";\s*\n", text) if s.strip()]:
        if "${app_sp}" in stmt and not APP_SP:
            print(f"SKIP (no app_sp): {stmt.splitlines()[0][:90]}")
            continue
        for k, v in subs.items():
            stmt = stmt.replace("${" + k + "}", v)
        spark.sql(stmt)
        print(f"OK   {stmt.splitlines()[0][:110]}")

# %% [markdown]
# ## 1. Governance functions (masks + row filter)

# %%
if PHASE in ("functions", "all"):
    run_sql_file("governance_functions.sql")

# %% [markdown]
# ## 2. Comments, tags and grants

# %%
if PHASE in ("post", "all"):
    run_sql_file("governance.sql")

# %% [markdown]
# ## 3. Verification

# %%
if PHASE in ("post", "all"):
    print("== Column masks and row filters bound to silver ==")
    show(f"""
      SELECT 'column_mask' AS policy, column_name, mask_name AS function_name
      FROM {CATALOG}.information_schema.column_masks
      WHERE table_schema = '{SCHEMA}' AND table_name = 'silver_otel_logs'
      UNION ALL
      SELECT 'row_filter', concat_ws(',', target_columns), filter_name
      FROM {CATALOG}.information_schema.row_filters
      WHERE table_schema = '{SCHEMA}' AND table_name = 'silver_otel_logs'
    """)
    print("\n== Table tags ==")
    show(f"""
      SELECT table_name, tag_name, tag_value FROM {CATALOG}.information_schema.table_tags
      WHERE schema_name = '{SCHEMA}' ORDER BY table_name, tag_name
    """)
    print("\n== Column tags ==")
    show(f"""
      SELECT table_name, column_name, tag_name, tag_value FROM {CATALOG}.information_schema.column_tags
      WHERE schema_name = '{SCHEMA}' ORDER BY table_name, column_name
    """)
    print("\n== Grants made on this schema and its tables (inherited catalog grants omitted) ==")
    show(f"""
      SELECT grantee, privilege_type, 'SCHEMA' AS object_type, schema_name AS object_name
      FROM {CATALOG}.information_schema.schema_privileges
      WHERE schema_name = '{SCHEMA}' AND inherited_from = 'NONE'
      UNION ALL
      SELECT grantee, privilege_type, 'TABLE', table_name
      FROM {CATALOG}.information_schema.table_privileges
      WHERE table_schema = '{SCHEMA}' AND inherited_from = 'NONE'
      ORDER BY object_type, object_name, grantee
    """)

# %%
if PHASE in ("post", "all"):
    print("== Masked read of silver (caller is not in helix_support_analysts) ==")
    show(f"""
      SELECT client_id, site_id, study_id, user_email, service_name, severity_text
      FROM {CATALOG}.{SCHEMA}.silver_otel_logs LIMIT 5
    """)
    print("\n== Row filter: isolated tenant wingtip-gx is in bronze but hidden in silver ==")
    show(f"""
      SELECT 'bronze' AS layer, count(*) AS wingtip_rows FROM {BRONZE}
      WHERE try_variant_get(attributes, '$["helix.client_id"]', 'string') = 'wingtip-gx'
      UNION ALL
      SELECT 'silver', count(*) FROM {CATALOG}.{SCHEMA}.silver_otel_logs WHERE client_id = 'wingtip-gx'
    """)

# %%
if PHASE in ("post", "all"):
    print("== Lineage captured by Unity Catalog (system.access.table_lineage) ==")
    show(f"""
      SELECT source_table_full_name, target_table_full_name, entity_type,
             max(event_time) AS last_seen
      FROM system.access.table_lineage
      WHERE target_table_catalog = '{CATALOG}' AND target_table_schema = '{SCHEMA}'
        AND source_table_full_name IS NOT NULL
      GROUP BY ALL ORDER BY target_table_full_name, source_table_full_name
    """)

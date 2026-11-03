# Lakeflow ingest: Fluent Bit → Zerobus (OTLP gRPC)

Zerobus is a **write API** (Lakeflow Connect), not a catalog connector (`CREATE CONNECTION`).
Kubernetes-style logs are tailed by Fluent Bit 5.x and posted as OTLP gRPC into a Unity Catalog
Delta table. The Spark Declarative Pipeline then starts at silver.

| Piece | Path |
|---|---|
| Fluent Bit OTLP gRPC client (the Zerobus writer) | `fluent-bit.yaml` |
| Bronze OTEL v2 DDL | `sql/create_bronze.sql` |
| Token mint (`authorization_details` for Zerobus) | `scripts/mint_zerobus_token.py` |
| Load-test runner | `scripts/run_load_test.sh` |
| Lakeflow Spark Declarative Pipeline (silver + gold) | `resources/fluentbit_otel_etl.pipeline.yml`, `src/fluentbit_otel_etl/transformations/` |
| Evidence | `evidence/01_ingest_load_test.log`, `evidence/02_pipeline_and_tables.md` |

Host pattern: `{workspace_id}.zerobus.{region}.cloud.databricks.com:443`.

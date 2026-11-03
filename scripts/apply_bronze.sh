#!/usr/bin/env bash
# Create accessdemo.fluentbit.helix_otel_logs if it does not exist (profile fevm-ai).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROFILE="${DATABRICKS_CONFIG_PROFILE:-fevm-ai}"

databricks experimental aitools tools query \
  --profile "$PROFILE" \
  --file "$ROOT/sql/create_bronze.sql"

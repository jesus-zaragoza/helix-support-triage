#!/usr/bin/env bash
# Mint a Zerobus token, start Fluent Bit (OTLP gRPC), then generate logs at 1.3 TB/day equivalent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

MBPS="${MBPS:-15}"
DURATION="${DURATION:-300}"
FIFO="${FIFO:-0}"
SMOKE="${SMOKE:-0}"

: "${DATABRICKS_HOST:?set DATABRICKS_HOST in .env}"
: "${WORKSPACE_ID:?set WORKSPACE_ID in .env}"
: "${REGION:?set REGION in .env}"
: "${DATABRICKS_LOGS_TABLE:?set DATABRICKS_LOGS_TABLE in .env}"
: "${DATABRICKS_CLIENT_ID:?set DATABRICKS_CLIENT_ID in .env}"
: "${DATABRICKS_CLIENT_SECRET:?set DATABRICKS_CLIENT_SECRET in .env}"

export LOG_PATH="${LOG_PATH:-$ROOT/logs/otel.jsonl}"
export FLB_DB_PATH="${FLB_DB_PATH:-$ROOT/logs/flb.db}"
mkdir -p "$ROOT/logs"

if ! command -v fluent-bit >/dev/null 2>&1; then
  echo "fluent-bit not found on PATH" >&2
  exit 1
fi

echo "Minting Zerobus OTLP token..."
TOKEN="$(python3 "$ROOT/scripts/mint_zerobus_token.py")"
export DATABRICKS_OTLP_TOKEN="$TOKEN"

FLB_PID=""
cleanup() {
  if [[ -n "$FLB_PID" ]] && kill -0 "$FLB_PID" 2>/dev/null; then
    kill "$FLB_PID" 2>/dev/null || true
    wait "$FLB_PID" 2>/dev/null || true
  fi
  # The JSONL is only a staging buffer. Drop it so Ctrl+C does not leave hundreds of MB on disk.
  if [[ "${FIFO:-0}" == "1" ]]; then
    rm -f "$LOG_PATH"
  elif [[ -f "${LOG_PATH:-}" ]]; then
    : > "$LOG_PATH"
  fi
}
trap cleanup EXIT

if [[ "$SMOKE" == "1" ]]; then
  export SMOKE_TEST_ID="${SMOKE_TEST_ID:-$(date +%s)}"
  echo "Starting Fluent Bit smoke (dummy → gRPC)..."
  fluent-bit -c "$ROOT/fluent-bit.smoke.yaml"
  exit 0
fi

rm -f "$FLB_DB_PATH" "$FLB_DB_PATH-shm" "$FLB_DB_PATH-wal"
GEN_ARGS=(--path "$LOG_PATH" --mbps "$MBPS" --duration "$DURATION")
if [[ "$FIFO" == "1" ]]; then
  rm -f "$LOG_PATH"
  python3 - <<PY
import os
os.mkfifo("$LOG_PATH", 0o600)
PY
  GEN_ARGS+=(--fifo)
else
  : > "$LOG_PATH"
fi

echo "Starting Fluent Bit (gRPC ${WORKSPACE_ID}.zerobus.${REGION}.cloud.databricks.com:443)..."
fluent-bit -c "$ROOT/fluent-bit.yaml" &
FLB_PID=$!
sleep 1
if ! kill -0 "$FLB_PID" 2>/dev/null; then
  echo "Fluent Bit failed to start" >&2
  exit 1
fi

echo "Generating logs at ${MBPS} MB/s for ${DURATION}s (1.3 TB/day ≈ 15 MB/s)..."
python3 "$ROOT/scripts/generate_otel_logs.py" "${GEN_ARGS[@]}"

# Wait until Fluent Bit has read the whole staging file, then let it flush the last chunks.
if [[ "$FIFO" != "1" ]] && command -v sqlite3 >/dev/null 2>&1; then
  FILE_SIZE="$(stat -f %z "$LOG_PATH" 2>/dev/null || stat -c %s "$LOG_PATH")"
  DEADLINE=$(( $(date +%s) + ${DRAIN_TIMEOUT:-600} ))
  while (( $(date +%s) < DEADLINE )); do
    OFFSET="$(sqlite3 "$FLB_DB_PATH" "SELECT COALESCE(MAX(offset),0) FROM in_tail_files;" 2>/dev/null || echo 0)"
    echo "drain: fluent-bit offset ${OFFSET} / ${FILE_SIZE} bytes"
    (( OFFSET >= FILE_SIZE )) && break
    sleep 10
  done
fi
sleep "${FLUSH_GRACE:-15}"
echo "Load test finished. Fluent Bit stopping."

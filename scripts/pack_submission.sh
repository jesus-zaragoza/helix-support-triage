#!/usr/bin/env bash
# Build a text-only folder for the certification form.
# Select THIS folder in the browser (not the workspace root with .venv / .build).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-"$ROOT/submission"}"
rm -rf "$DEST"
mkdir -p "$DEST"

copy_tree() {
  local src="$1"
  if [[ -d "$ROOT/$src" ]]; then
    mkdir -p "$DEST/$src"
    rsync -a --exclude '__pycache__/' --exclude '*.pyc' --exclude '*.ipynb' "$ROOT/$src/" "$DEST/$src/"
  elif [[ -f "$ROOT/$src" ]]; then
    mkdir -p "$DEST/$(dirname "$src")"
    cp "$ROOT/$src" "$DEST/$src"
  fi
}

for p in \
  README.md SOURCE_MAP.md databricks.yml requirements-dev.txt .env.example .gitignore \
  fluent-bit.yaml fluent-bit.smoke.yaml \
  deck/helix-support-triage.md deck/helix-support-triage.pdf \
  evidence docs resources sql scripts \
  src/app src/config src/dashboard src/fluentbit_otel_etl src/genie src/lakebase src/notebooks \
  samples/token-broker
do
  copy_tree "$p"
done

# notebooks dir may still have .ipynb if rsync exclude missed; strip them
find "$DEST" -name '*.ipynb' -delete
find "$DEST" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

cat > "$DEST/SELECT_THIS_FOLDER.txt" <<'EOF'
Certification form: choose THIS folder (submission/), not the parent workspace.

The parent tree contains .venv and .build, which fill the upload quota so Lakeflow
and Lakebase sources never arrive. This pack is text (.py .sql .yml .md .log) plus
the deck PDF. Start at SOURCE_MAP.md.
EOF

echo "packed $DEST"
find "$DEST" -type f | wc -l
du -sh "$DEST"
find "$DEST" -type f | sed "s|$DEST/||" | sort

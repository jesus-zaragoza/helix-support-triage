-- Lakebase native Postgres table written by the Support Console (src/app/app.py).
-- The three gold tables are SNAPSHOT-synced from Delta (src/lakebase/sync.py) into
-- schema <uc_schema> as lb_gold_client_health / lb_gold_client_anomalies / lb_gold_incident_briefs.
-- triage_notes is app-owned operational state, not a synced Delta table.

CREATE SCHEMA IF NOT EXISTS support_app;

CREATE TABLE IF NOT EXISTS support_app.triage_notes (
  note_id      BIGSERIAL PRIMARY KEY,
  ticket_id    TEXT NOT NULL,
  client_id    TEXT NOT NULL,
  incident_id  TEXT,
  status       TEXT NOT NULL DEFAULT 'investigating',
  note         TEXT NOT NULL,
  author       TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS triage_notes_client_idx
  ON support_app.triage_notes (client_id, created_at DESC);

"""Helix Support Console — Databricks App (FastAPI).

Reads client health, model-flagged anomalies and AI incident briefs from Lakebase synced
tables, writes triage notes to a Lakebase table owned by the app, and proxies natural
language questions to the Helix Genie Agent.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

SYNC_SCHEMA = os.environ.get("SYNC_SCHEMA", "dev_jesus_zaragoza_helix_support")
APP_SCHEMA = os.environ.get("APP_SCHEMA", "support_app")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "")
LAKEBASE_ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT", "")

w = WorkspaceClient()
app = FastAPI(title="Helix Support Console")
_token: dict[str, Any] = {"value": None, "expires": 0.0}
_lock = threading.Lock()


def _pg_password() -> str:
    with _lock:
        if not _token["value"] or time.time() > _token["expires"]:
            cred = w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT)
            _token["value"] = cred.token
            _token["expires"] = time.time() + 45 * 60
        return _token["value"]


@contextmanager
def pg():
    conn = psycopg2.connect(
        host=os.environ["PGHOST"],
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "databricks_postgres"),
        user=os.environ.get("PGUSER") or w.config.client_id,
        password=_pg_password(),
        sslmode=os.environ.get("PGSSLMODE", "require"),
        connect_timeout=15,
    )
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    with pg() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else []
    return [{k: _jsonable(v) for k, v in r.items()} for r in rows]


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def sync(table: str) -> str:
    return f'"{SYNC_SCHEMA}"."lb_{table}"'


@app.on_event("startup")
def init_schema() -> None:
    # The app's service principal creates (and owns) its own schema for writable state.
    with pg() as conn, conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{APP_SCHEMA}"')
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS "{APP_SCHEMA}".triage_notes (
              note_id      BIGSERIAL PRIMARY KEY,
              ticket_id    TEXT NOT NULL,
              client_id    TEXT NOT NULL,
              incident_id  TEXT,
              status       TEXT NOT NULL DEFAULT 'investigating',
              note         TEXT NOT NULL,
              author       TEXT NOT NULL,
              created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        cur.execute(f'CREATE INDEX IF NOT EXISTS triage_notes_client_idx ON "{APP_SCHEMA}".triage_notes (client_id, created_at DESC)')


@app.get("/api/health")
def health() -> dict:
    row = query("SELECT now() AS db_time, current_user AS db_user")[0]
    return {"status": "ok", "lakebase": row, "genie_space_id": GENIE_SPACE_ID or None}


@app.get("/api/clients")
def clients() -> list[dict]:
    return query(f"""
        WITH h AS (
          SELECT client_id, client_name, SUM(event_count) AS events, SUM(error_count) AS errors,
                 MAX(window_start) AS last_window
          FROM {sync('gold_client_health')} GROUP BY client_id, client_name
        ),
        a AS (SELECT client_id, COUNT(*) AS anomalous_windows FROM {sync('gold_client_anomalies')} GROUP BY client_id),
        b AS (
          SELECT client_id, COUNT(*) AS incidents,
                 MIN(CASE severity WHEN 'SEV1' THEN 1 WHEN 'SEV2' THEN 2 ELSE 3 END) AS worst
          FROM {sync('gold_incident_briefs')} GROUP BY client_id
        )
        SELECT h.client_id, h.client_name, h.events, h.errors,
               ROUND(h.errors::numeric / NULLIF(h.events, 0), 4) AS error_rate, h.last_window,
               COALESCE(a.anomalous_windows, 0) AS anomalous_windows, COALESCE(b.incidents, 0) AS incidents,
               CASE b.worst WHEN 1 THEN 'SEV1' WHEN 2 THEN 'SEV2' WHEN 3 THEN 'SEV3' END AS worst_severity
        FROM h LEFT JOIN a USING (client_id) LEFT JOIN b USING (client_id)
        ORDER BY COALESCE(b.worst, 9), h.errors DESC""")


@app.get("/api/clients/{client_id}")
def client_detail(client_id: str) -> dict:
    timeline = query(f"""
        SELECT date_trunc('hour', window_start) AS hour, SUM(event_count) AS events,
               SUM(error_count) AS errors, MAX(p95_latency_ms) AS max_p95_latency_ms
        FROM {sync('gold_client_health')} WHERE client_id = %s
        GROUP BY 1 ORDER BY 1""", (client_id,))
    sites = query(f"""
        SELECT site_id, service_name, SUM(event_count) AS events,
               ROUND(SUM(error_count)::numeric / NULLIF(SUM(event_count), 0), 4) AS error_rate,
               MAX(p95_latency_ms) AS max_p95_latency_ms
        FROM {sync('gold_client_health')} WHERE client_id = %s
        GROUP BY site_id, service_name ORDER BY error_rate DESC LIMIT 25""", (client_id,))
    anomalies = query(f"""
        SELECT window_start, site_id, service_name, error_rate, p95_latency_ms, top_error_signature,
               anomaly_score, model_version
        FROM {sync('gold_client_anomalies')} WHERE client_id = %s
        ORDER BY anomaly_score DESC LIMIT 50""", (client_id,))
    briefs = query(f"""
        SELECT incident_id, severity, started_at, ended_at, sites, services, peak_error_rate,
               peak_p95_latency_ms, summary, likely_cause, recommended_next_step, client_reply, model_endpoint
        FROM {sync('gold_incident_briefs')} WHERE client_id = %s ORDER BY started_at DESC""", (client_id,))
    notes = query(f"""SELECT * FROM "{APP_SCHEMA}".triage_notes WHERE client_id = %s
                      ORDER BY created_at DESC LIMIT 50""", (client_id,))
    if not timeline:
        raise HTTPException(404, f"unknown client {client_id}")
    return {"client_id": client_id, "timeline": timeline, "sites": sites,
            "anomalies": anomalies, "briefs": briefs, "notes": notes}


@app.get("/api/briefs")
def briefs() -> list[dict]:
    return query(f"""SELECT incident_id, client_id, client_name, severity, started_at, ended_at, sites,
                            services, peak_error_rate, summary, likely_cause, recommended_next_step, client_reply
                     FROM {sync('gold_incident_briefs')} ORDER BY started_at""")


class NoteIn(BaseModel):
    ticket_id: str = Field(..., min_length=1, max_length=64)
    client_id: str = Field(..., min_length=1, max_length=64)
    incident_id: str | None = None
    status: str = Field("investigating", pattern="^(investigating|mitigated|resolved|escalated)$")
    note: str = Field(..., min_length=1, max_length=4000)
    author: str = Field("support-console", max_length=200)


@app.post("/api/notes")
def add_note(n: NoteIn) -> dict:
    return query(f"""INSERT INTO "{APP_SCHEMA}".triage_notes (ticket_id, client_id, incident_id, status, note, author)
                     VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
                 (n.ticket_id, n.client_id, n.incident_id, n.status, n.note, n.author))[0]


@app.get("/api/notes")
def list_notes(client_id: str | None = None) -> list[dict]:
    if client_id:
        return query(f'SELECT * FROM "{APP_SCHEMA}".triage_notes WHERE client_id = %s ORDER BY created_at DESC', (client_id,))
    return query(f'SELECT * FROM "{APP_SCHEMA}".triage_notes ORDER BY created_at DESC LIMIT 100')


class Question(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    conversation_id: str | None = None


@app.post("/api/genie")
def ask_genie(q: Question) -> dict:
    if not GENIE_SPACE_ID:
        raise HTTPException(503, "Genie space not configured")
    if q.conversation_id:
        msg = w.genie.create_message_and_wait(GENIE_SPACE_ID, q.conversation_id, q.question)
    else:
        msg = w.genie.start_conversation_and_wait(GENIE_SPACE_ID, q.question)
    out: dict[str, Any] = {"conversation_id": msg.conversation_id, "message_id": msg.message_id,
                           "status": msg.status.value if msg.status else None, "text": None,
                           "sql": None, "description": None, "columns": [], "rows": []}
    for att in msg.attachments or []:
        if att.text and att.text.content:
            out["text"] = att.text.content
        if att.query:
            out["sql"] = att.query.query
            out["description"] = att.query.description
            res = w.genie.get_message_attachment_query_result(
                GENIE_SPACE_ID, msg.conversation_id, msg.message_id, att.attachment_id)
            sr = res.statement_response
            if sr and sr.manifest and sr.manifest.schema:
                out["columns"] = [c.name for c in sr.manifest.schema.columns or []]
            if sr and sr.result and sr.result.data_array:
                out["rows"] = sr.result.data_array[:50]
    return out


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")

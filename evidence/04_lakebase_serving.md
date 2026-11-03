# Lakebase operational serving evidence

Lakebase Autoscaling project `helix-support`, branch `production`, database `databricks_postgres`. Gold Delta tables are synced (SNAPSHOT) into Postgres schema `dev_jesus_zaragoza_helix_support` as `lb_*`; the app writes triage notes to `support_app.triage_notes`.

Grants issued to the app service principal role: USAGE on the synced schema, SELECT on its tables (plus default privileges for future syncs).

```sql
SELECT table_schema, table_name, (xpath('/row/c/text()',
       query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name), false, true, '')))[1]::text::bigint AS row_count
FROM information_schema.tables
WHERE table_schema IN ('dev_jesus_zaragoza_helix_support', 'support_app')
ORDER BY 1, 2
```

| table_schema | table_name | row_count |
|---|---|---|
| dev_jesus_zaragoza_helix_support | lb_gold_client_anomalies | 130 |
| dev_jesus_zaragoza_helix_support | lb_gold_client_health | 26010 |
| dev_jesus_zaragoza_helix_support | lb_gold_incident_briefs | 10 |
| support_app | triage_notes | 2 |

```sql
SELECT client_name, round(100.0 * sum(error_count) / sum(event_count), 2) AS error_rate_pct,
       sum(event_count) AS events
FROM "dev_jesus_zaragoza_helix_support".lb_gold_client_health GROUP BY client_name ORDER BY error_rate_pct DESC
```

| client_name | error_rate_pct | events |
|---|---|---|
| Fabrikam CRO | 1.69 | 360332 |
| Contoso Therapeutics | 1.58 | 294057 |
| Northwind Bio | 1.54 | 327302 |
| Tailspin Oncology | 1.51 | 229639 |
| Adatum Clinical Research | 1.48 | 229502 |

```sql
SELECT incident_id, client_name, severity, started_at, ended_at
FROM "dev_jesus_zaragoza_helix_support".lb_gold_incident_briefs ORDER BY severity, started_at
```

| incident_id | client_name | severity | started_at | ended_at |
|---|---|---|---|---|
| contoso-tx-20261102-0910 | Contoso Therapeutics | SEV1 | 2026-11-02 09:10:00+00:00 | 2026-11-02 10:00:00+00:00 |
| fabrikam-cro-20261102-1740 | Fabrikam CRO | SEV1 | 2026-11-02 17:40:00+00:00 | 2026-11-02 19:15:00+00:00 |
| northwind-bio-20261102-0310 | Northwind Bio | SEV2 | 2026-11-02 03:10:00+00:00 | 2026-11-02 03:45:00+00:00 |
| adatum-clin-20261102-0425 | Adatum Clinical Research | SEV2 | 2026-11-02 04:25:00+00:00 | 2026-11-02 04:40:00+00:00 |
| adatum-clin-20261102-0510 | Adatum Clinical Research | SEV2 | 2026-11-02 05:10:00+00:00 | 2026-11-02 05:30:00+00:00 |
| fabrikam-cro-20261102-1335 | Fabrikam CRO | SEV2 | 2026-11-02 13:35:00+00:00 | 2026-11-02 13:55:00+00:00 |
| northwind-bio-20261102-1505 | Northwind Bio | SEV2 | 2026-11-02 15:05:00+00:00 | 2026-11-02 15:15:00+00:00 |
| fabrikam-cro-20261102-1630 | Fabrikam CRO | SEV2 | 2026-11-02 16:30:00+00:00 | 2026-11-02 16:35:00+00:00 |
| fabrikam-cro-20261102-0010 | Fabrikam CRO | SEV3 | 2026-11-02 00:10:00+00:00 | 2026-11-02 00:15:00+00:00 |
| adatum-clin-20261102-2125 | Adatum Clinical Research | SEV3 | 2026-11-02 21:25:00+00:00 | 2026-11-02 21:45:00+00:00 |

```sql
SELECT note_id, ticket_id, client_id, incident_id, status, author, left(note, 80) AS note, created_at
FROM support_app.triage_notes ORDER BY note_id DESC
```

| note_id | ticket_id | client_id | incident_id | status | author | note | created_at |
|---|---|---|---|---|---|---|---|
| 2 | SUP-4813 | contoso-tx | contoso-tx-20261102-0910 | resolved | support-analyst-demo | E-signature vendor confirmed 503 outage 09:05-09:58 UTC; circuit breaker enabled | 2026-11-03 01:22:59.911723+00:00 |
| 1 | SUP-4812 | fabrikam-cro | fabrikam-cro-20261102-1740 | mitigated | support-analyst-demo | Confirmed DICOM association rejects at site-204; failed over router pool, upload | 2026-11-03 00:53:05.915395+00:00 |


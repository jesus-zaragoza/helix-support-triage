# Databricks App evidence: Helix Support Console

App `helix-support-console` (FastAPI on Databricks Apps), compute `ACTIVE`, deployment `01f1d720c01410a5b35be1957327847c`. Resources: Lakebase `postgres` (CAN_CONNECT_AND_CREATE), `sql-warehouse` (CAN_USE), `genie-space` (CAN_RUN). Calls below were made with a workspace OAuth token against the live app.

### `GET /api/health`

Request:

```
GET /api/health
```

Response (HTTP 200):

```json
{
  "status": "ok",
  "lakebase": {
    "db_time": "2026-11-03T01:22:59.042536+00:00",
    "db_user": "<app-sp>"
  },
  "genie_space_id": "01f1d71fa1d31031988b8348914796c3"
}
```

### `GET /api/clients`

Request:

```
GET /api/clients
```

Response (HTTP 200):

```json
[
  {
    "client_id": "fabrikam-cro",
    "client_name": "Fabrikam CRO",
    "events": 360332.0,
    "errors": 6092.0,
    "error_rate": 0.0169,
    "last_window": "2026-11-03T00:10:00+00:00",
    "anomalous_windows": 59,
    "incidents": 4,
    "worst_severity": "SEV1"
  },
  {
    "client_id": "contoso-tx",
    "client_name": "Contoso Therapeutics",
    "events": 294057.0,
    "errors": 4639.0,
    "error_rate": 0.0158,
    "last_window": "2026-11-03T00:10:00+00:00",
    "anomalous_windows": 36,
    "incidents": 1,
    "worst_severity": "SEV1"
  },
  {
    "client_id": "northwind-bio",
    "client_name": "Northwind Bio",
    "events": 327302.0,
    "errors": 5047.0,
    "error_rate": 0.0154,
    "last_window": "2026-11-03T00:10:00+00:00",
    "anomalous_windows": 11,
    "incidents": 2,
    "worst_severity": "SEV2"
  },
  {
    "client_id": "adatum-clin",
    "client_name": "Adatum Clinical Research",
    "events": 229502.0,
    "errors": 3403.0,
    "error_rate": 0.0148,
    "last_window": "2026-11-03T00:10:00+00:00",
    "anomalous_windows": 21,
    "incidents": 3,
    "worst_severity": "SEV2"
  },
  {
    "client_id": "tailspin-onc",
    "client_name": "Tailspin Oncology",
    "events": 229639.0,
    "errors": 3461.0,
    "error_rate": 0.0151,
    "last_window": "2026-11-03T00:10:00+00:00",
    "anomalous_windows": 3,
    "incidents": 0,
    "worst_severity": null
  }
]
```

### `GET /api/clients/fabrikam-cro`

Request:

```
GET /api/clients/fabrikam-cro
```

Response (HTTP 200):

```json
{
  "client_id": "fabrikam-cro",
  "timeline_hours": 25,
  "worst_hours": [
    {
      "hour": "2026-11-02T18:00:00+00:00",
      "events": 15115.0,
      "errors": 667.0,
      "max_p95_latency_ms": 3690.6
    },
    {
      "hour": "2026-11-02T17:00:00+00:00",
      "events": 15191.0,
      "errors": 352.0,
      "max_p95_latency_ms": 2942.6
    },
    {
      "hour": "2026-11-02T19:00:00+00:00",
      "events": 14796.0,
      "errors": 316.0,
      "max_p95_latency_ms": 2996.3
    }
  ],
  "sites": [
    {
      "site_id": "site-204",
      "service_name": "trial-upload-api",
      "events": 18293.0,
      "error_rate": 0.035,
      "max_p95_latency_ms": 3690.6
    },
    {
      "site_id": "site-204",
      "service_name": "dicom-router",
      "events": 16093.0,
      "error_rate": 0.0335,
      "max_p95_latency_ms": 1557.4
    },
    {
      "site_id": "site-203",
      "service_name": "dicom-router",
      "events": 15959.0,
      "error_rate": 0.0179,
      "max_p95_latency_ms": 262.6
    },
    {
      "site_id": "site-202",
      "service_name": "imaging-archive",
      "events": 21772.0,
      "error_rate": 0.0165,
      "max_p95_latency_ms": 515.0
    },
    {
      "site_id": "site-203",
      "service_name": "trial-upload-api",
      "events": 17626.0,
      "error_rate": 0.0164,
      "max_p95_latency_ms": 764.1
    }
  ],
  "anomalies_count": 50,
  "briefs": [
    {
      "incident_id": "fabrikam-cro-20261102-1740",
      "severity": "SEV1",
      "started_at": "2026-11-02T17:40:00+00:00",
      "ended_at": "2026-11-02T19:15:00+00:00",
      "client_reply": "Dear Fabrikam CRO Team, we are aware that your sites experienced difficulties submitting DICOM images and trial data uploads between approximately 17:40 and 19:15 UTC today, and we sincerely apologize for the disruption to your study operations. Our engineering team has identified the affected services and is actively investigating the root cause; we are closely monitoring all systems and will provide a further update within the hour. No action is required from your site coordinators at this time \u2014 any submissions that did not complete successfully can be safely retried, and we will confirm when the environment is fully stable. Please do not hesitate to reach out if you have any immediate concerns."
    },
    {
      "incident_id": "fabrikam-cro-20261102-1630",
      "severity": "SEV2",
      "started_at": "2026-11-02T16:30:00+00:00",
      "ended_at": "2026-11-02T16:35:00+00:00",
      "client_reply": "Dear Fabrikam CRO Site Coordination Team, we are aware that users at sites 202 and 204 experienced intermittent errors and delays within the eConsent application between approximately 16:30 and 16:35 UTC today. Our engineering team has identified the affected components and is actively investigating the root cause; we are closely monitoring the platform to ensure full stability is maintained. We will provide a further update within the hour, and please do not hesitate to reach out if any participants are still unable to complete their consent workflows. Thank you for your patience."
    },
    {
      "incident_id": "fabrikam-cro-20261102-1335",
      "severity": "SEV2",
      "started_at": "2026-11-02T13:35:00+00:00",
      "ended_at": "2026-11-02T13:55:00+00:00",
      "client_reply": "Dear Fabrikam CRO Site Coordination Team, we are aware that some users at your sites experienced intermittent login difficulties and authentication delays between approximately 13:35 and 13:55 UTC today. Our engineering team has identified the likely source and is actively working to fully resolve the issue and prevent recurrence. Services appear to have stabilised, and we are continuing to monitor closely. We will provide a follow-up update within the hour, and please do not hesitate to reach out if any users are still experiencing issues. Thank you for your patience."
    },
    {
      "incident_id": "fabrikam-cro-20261102-0010",
      "severity": "SEV3",
      "started_at": "2026-11-02T00:10:00+00:00",
      "ended_at": "2026-11-02T00:15:00+00:00",
      "client_reply": "Dear Fabrikam CRO Site Coordination Team, we want to let you know that between approximately 00:10 and 00:15 UTC today, a small number of users across your sites may have encountered slower-than-normal login responses or brief delays when uploading imaging data. Our systems detected and logged the anomaly automatically, and conditions returned to normal within approximately five minutes. Our engineering team is actively monitoring the platform to confirm full stability and to identify the root cause. No clinical data was lost, and all submissions should be retried safely if you received an error prompt. We will provide a follow-up update within two hours. Please don't hesitate to reach out if any of your coordinators are still experiencing issues. Thank you for your patience."
    }
  ],
  "notes": [
    {
      "note_id": 1,
      "ticket_id": "SUP-4812",
      "client_id": "fabrikam-cro",
      "incident_id": "fabrikam-cro-20261102-1740",
      "status": "mitigated",
      "note": "Confirmed DICOM association rejects at site-204; failed over router pool, uploads recovering. Sent AI draft reply to site coordinator.",
      "author": "support-analyst-demo",
      "created_at": "2026-11-03T00:53:05.915395+00:00"
    }
  ]
}
```

### `POST /api/notes`

Request:

```
POST /api/notes
{
  "ticket_id": "SUP-4813",
  "client_id": "contoso-tx",
  "incident_id": "contoso-tx-20261102-0910",
  "status": "resolved",
  "author": "support-analyst-demo",
  "note": "E-signature vendor confirmed 503 outage 09:05-09:58 UTC; circuit breaker enabled, AI draft reply sent to all 3 sites."
}
```

Response (HTTP 200):

```json
{
  "note_id": 2,
  "ticket_id": "SUP-4813",
  "client_id": "contoso-tx",
  "incident_id": "contoso-tx-20261102-0910",
  "status": "resolved",
  "note": "E-signature vendor confirmed 503 outage 09:05-09:58 UTC; circuit breaker enabled, AI draft reply sent to all 3 sites.",
  "author": "support-analyst-demo",
  "created_at": "2026-11-03T01:22:59.911723+00:00"
}
```

### `GET /api/notes`

Request:

```
GET /api/notes
```

Response (HTTP 200):

```json
[
  {
    "note_id": 2,
    "ticket_id": "SUP-4813",
    "client_id": "contoso-tx",
    "incident_id": "contoso-tx-20261102-0910",
    "status": "resolved",
    "note": "E-signature vendor confirmed 503 outage 09:05-09:58 UTC; circuit breaker enabled, AI draft reply sent to all 3 sites.",
    "author": "support-analyst-demo",
    "created_at": "2026-11-03T01:22:59.911723+00:00"
  },
  {
    "note_id": 1,
    "ticket_id": "SUP-4812",
    "client_id": "fabrikam-cro",
    "incident_id": "fabrikam-cro-20261102-1740",
    "status": "mitigated",
    "note": "Confirmed DICOM association rejects at site-204; failed over router pool, uploads recovering. Sent AI draft reply to site coordinator.",
    "author": "support-analyst-demo",
    "created_at": "2026-11-03T00:53:05.915395+00:00"
  }
]
```

### `POST /api/genie`

Request:

```
POST /api/genie
{
  "question": "Which Fabrikam CRO services had the worst error rate between 17:00 and 19:30?"
}
```

Response (HTTP 200):

```json
{
  "conversation_id": "01f1d7251bcf16759a395fc00ab4cb54",
  "message_id": "01f1d7251be717e299242523a99d6c1f",
  "status": "COMPLETED",
  "text": "Between **17:00 and 19:30** in the last 24-hour timeline for **Fabrikam CRO**, the worst error rates were on **trial-upload-api** at **5.9%** and **dicom-router** at **5.7%**. Examples include:\n- **trial-upload-api** \u2014 **5.9%** error rate (**460** errors out of **7,805** events)\n- **dicom-router** \u2014 **5.7%** (**395** / **6,955**)\n- **imaging-archive** \u2014 **1.6%** (**150** / **9,394**)\n- **auth-api** \u2014 **1.5%** (**82** / **5,449**)\n- **ingress-gateway** \u2014 **1.5%** (**71** / **4,620**)\n\nAcross all **6** services shown, **trial-upload-api** and **dicom-router** stand out clearly, with error rates more than three times higher than the rest.",
  "sql": "SELECT h.`service_name`, SUM(h.`error_count`) AS `errors`, SUM(h.`event_count`) AS `events`, ROUND(try_divide(100.0 * SUM(h.`error_count`),SUM(h.`event_count`)), 1) AS `error_rate_pct` FROM `accessdemo`.`dev_jesus_zaragoza_helix_support`.`gold_client_health` h CROSS JOIN (SELECT MAX(`window_start`) AS `max_ts` FROM `accessdemo`.`dev_jesus_zaragoza_helix_support`.`gold_client_health`) mx WHERE h.`client_name` = 'Fabrikam CRO' AND h.`service_name` IS NOT NULL AND h.`window_start` >= mx.`max_ts` - INTERVAL 24 HOURS AND (HOUR(h.`window_start`) > 17 OR (HOUR(h.`window_start`) = 17 AND MINUTE(h.`window_start`) >= 0)) AND (HOUR(h.`window_start`) < 19 OR (HOUR(h.`window_start`) = 19 AND MINUTE(h.`window_start`) <= 30)) GROUP BY h.`service_name` HAVING SUM(h.`event_count`) > 0 ORDER BY `error_rate_pct` DESC, `errors` DESC, h.`service_name`",
  "description": "You want to see which services of Fabrikam CRO had the highest error rates between 17:00 and 19:30 in the last 24 hours relative to the latest data timestamp.",
  "columns": [
    "service_name",
    "errors",
    "events",
    "error_rate_pct"
  ],
  "rows": [
    [
      "trial-upload-api",
      "460",
      "7805",
      "5.9"
    ],
    [
      "dicom-router",
      "395",
      "6955",
      "5.7"
    ],
    [
      "imaging-archive",
      "150",
      "9394",
      "1.6"
    ],
    [
      "auth-api",
      "82",
      "5449",
      "1.5"
    ],
    [
      "ingress-gateway",
      "71",
      "4620",
      "1.5"
    ],
    [
      "econsent-web",
      "67",
      "4656",
      "1.4"
    ]
  ]
}
```


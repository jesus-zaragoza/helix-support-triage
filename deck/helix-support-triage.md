# Helix Support Console

**Client tickets answered by Support in minutes, without paging engineering**

Life-sciences client support triage on Databricks: Lakeflow, Unity Catalog, Lakebase, MLflow + AI Functions, Genie and Databricks Apps.

*Audience: VP Customer Success (executive sponsor), CTO, Support lead and SRE lead (domain owners).*

*Helix Clinical Cloud, its clients and all data in this deck are fictional and synthetic.*

<div style="page-break-after: always"></div>

## 1. The outcome

A support analyst who gets "site-204 can't upload scans" now opens **one app** and, within a minute, sees:

- the client's health by site and service, served from **Lakebase** (Postgres);
- whether the **ML model** flagged it, and when it started;
- an **AI incident brief** with likely cause, next step and a **ready-to-send client reply**;
- an **Ask Genie** box for follow-up questions in plain English;
- a **triage note** saved back to Lakebase for hand-off.

| Proven in the prototype (measured) | Result |
|---|---|
| Injected client incidents found by the anomaly model | **3 of 3** (recall 1.0, ROC AUC 0.9999) |
| Incidents with an AI brief and client reply | **10** (2 × SEV1, 6 × SEV2, 2 × SEV3) |
| Logs ingested end-to-end (Fluent Bit → Zerobus → Delta) | **1.64 M rows, 1.8 GB in 10 min, 0 failed flushes** |
| Other-tenant rows exposed to Support | **0** (row filter; 196 k isolated-tenant rows hidden) |
| Genie questions answered with correct SQL | **5 of 5** sample questions + app question |

<div style="page-break-after: always"></div>

## 2. The problem today

Helix runs imaging-archive, DICOM routing, trial-data upload and eConsent for pharma and CRO clients on Kubernetes.

- Logs go **disk → Vector → S3 → batch job → one untyped table**, more than **15 minutes late**.
- Support **cannot see application logs**. Every "my site's upload failed" ticket becomes an engineering escalation.
- Engineers grep raw logs per ticket; client communication waits on them.
- Missed clinical-trial milestones turn into **SLA breaches and service credits**.
- Scale: about **4.17 B log rows / 1.3 TB per day**, roughly **48 k lines per second** at peak.

<div style="page-break-after: always"></div>

## 3. KPIs: baseline and target

| KPI | Baseline (today) | Target (90 days after rollout) | How it is measured |
|---|---|---|---|
| Mean time to triage a client ticket | ~4 h (wait for engineer) | **< 15 min** | ticket open → first triage note in `triage_notes` |
| Engineering escalation rate | ~70 % of app tickets | **< 25 %** | tickets with no engineering assignee |
| SLA breaches / service credits | quarterly credits on SEV1s | **−50 %** | SEV1 duration from `gold_incident_briefs` |
| Log freshness for Support | > 15 min, batch | **< 1 min** bronze, < 5 min gold | `ingest_time − event_time` in silver |
| Log pipeline infrastructure | Vector fleet + S3 staging + batch job | **Remove Vector and S3 hops** | Fluent Bit writes straight to Zerobus |

*Baselines are planning assumptions to be confirmed with Helix's ticketing data in week 1. The targets are what the pilot is meant to prove.*

<div style="page-break-after: always"></div>

## 4. Value by audience

**Executive sponsor: VP Customer Success / CTO**

- Client-facing answers in minutes protect renewals with top pharma and CRO accounts.
- Fewer SLA credits; SEV1s are detected by the model rather than reported by the client.
- One governed platform instead of Vector + S3 + a separate log store: lower run cost and fewer moving parts.
- Isolation by client is enforced by Unity Catalog policy, not by convention, which keeps audits simple.

**Domain owner: Support lead / SRE lead**

- Support self-serves: health, anomalies, cause and reply text in one place.
- SRE gets fewer pages and a shared timeline (anomaly windows plus triage notes) when an escalation is needed.
- Genie answers ad-hoc questions ("worst site for uploads today?") without a dashboard request.
- Masked PII (coordinator email, study id) by default; privileged groups see full values.

<div style="page-break-after: always"></div>

## 5. Architecture

```text
K8s app pods (synthetic generator)
   │ container log files
   ▼
Fluent Bit 5.1 ─OTLP gRPC─▶ Zerobus (Lakeflow Connect)
   ▼
UC bronze: OTEL v2 Delta table
   ▼  Lakeflow Spark Declarative Pipeline (serverless)
silver_otel_logs   typed, deduped, column masks, row filter
   ▼
gold_client_health · incident_summary · error_signatures
   │                     │                      │
   ▼                     ▼                      ▼
MLflow IsolationForest  ai_query (Claude)    Genie Agent
gold_client_anomalies   gold_incident_briefs (trusted SQL)
   │                     │                      │
   └──▶ Lakebase synced tables (Postgres) ◀──┘  │
                 │                              │
                 ▼                              ▼
       Databricks App "Support Console" (FastAPI)
                 └── writes triage_notes ─▶ Lakebase
```

One Lakeflow Job (in a Declarative Automation Bundle) runs the chain: pipeline refresh → governance → train and score → AI briefs → Lakebase sync.

<div style="page-break-after: always"></div>

## 6. What each Databricks capability does

| Stage | Capability | What it does for Support |
|---|---|---|
| Ingest | **Lakeflow Connect: Zerobus** (OTLP gRPC) | Logs land in Delta seconds after they are written; no Vector or S3 |
| Transform | **Lakeflow Spark Declarative Pipelines** | Typed silver with expectations and dedup; gold health in 5-minute windows |
| Govern | **Unity Catalog** | Column masks, client row filter, tags, grants, end-to-end lineage |
| Detect | **MLflow + UC model registry** | IsolationForest flags abnormal client/site/service windows |
| Explain | **AI Functions (`ai_query`)** | Structured brief: severity, cause, next step, client reply |
| Serve | **Lakebase** (synced tables + native table) | Millisecond app reads; triage notes written back |
| Ask | **Genie Agent** | Natural-language questions with trusted SQL and instructions |
| Act | **Databricks Apps** | Support Console with SSO and service-principal-scoped access |

<div style="page-break-after: always"></div>

## 7. Demo flow (5 minutes)

1. **Client list**: Fabrikam CRO and Contoso Therapeutics are at the top with SEV1.
2. **Fabrikam CRO**: hourly error bars spike 17:40–19:15; site-204 trial-upload-api and dicom-router are at 44 % errors at peak.
3. **Brief**: "DICOM association rejected / upload timeout" with a recommended router fail-over and a client reply ready to send.
4. **Triage note**: the analyst logs SUP-4812 as *mitigated*; it is stored in Lakebase `support_app.triage_notes`.
5. **Ask Genie**: "Which Fabrikam CRO services had the worst error rate between 17:00 and 19:30?" returns trial-upload-api 5.9 % and dicom-router 5.7 %, with the SQL shown.
6. **Governance**: the same silver query shows `***@client.example` emails, and the isolated tenant is invisible.

<div style="page-break-after: always"></div>

## 8. Evidence from the prototype run

| Measure | Value |
|---|---|
| Load test | 600 s, 3 MB/s, 24 simulated hours, 2,879 HTTP 200 flushes, 0 failures |
| Bronze → silver | 1,637,120 rows → 1,440,832 visible rows (isolated tenant filtered) |
| Gold health windows | 26,010 client/site/service 5-minute windows |
| Anomaly model (v1 champion) | precision 0.53, recall 1.00, average precision 0.95, 130 windows flagged |
| AI briefs | 10 incidents; both SEV1s match injected incidents; the archive slowdown was attributed to S3 |
| Lakebase | 3 synced tables online plus `triage_notes`; app reads and writes verified |
| Genie | 6 questions, all answered with correct SQL |

The model is deliberately tuned for recall: missing a client incident costs far more than reviewing a false alarm. The briefs show severity, so analysts start with SEV1.

<div style="page-break-after: always"></div>

## 9. Rollout plan

| Phase | Weeks | Scope | Exit criteria |
|---|---|---|---|
| Pilot | 1–4 | One region, 2 clients, Support pod of 5 | Triage time < 30 min; analysts prefer the console |
| Expand | 5–8 | All US clients; Fluent Bit DaemonSet replaces Vector | Freshness < 1 min at 48 k lines/s; zero data loss |
| Scale | 9–12 | Non-US regions; ticketing integration (note ↔ ticket) | Escalations < 25 %; SLA-credit trend down |
| Operate | 12+ | Retrain model monthly; Genie benchmarks in CI | Model precision ≥ 0.7 on labeled incidents |

**Risks and mitigations:** Zerobus token lifecycle (token broker sample in repo); false positives (severity triage, human in the loop); PII in logs (UC masks, tags, audit).

<div style="page-break-after: always"></div>

## 10. The ask

1. **Sponsor**: approve a 4-week pilot with two clients and one Support pod.
2. **Support lead**: name 5 pilot analysts and share a month of ticket data to confirm the baseline KPIs.
3. **SRE lead**: deploy the Fluent Bit DaemonSet to one cluster in parallel with Vector.
4. **Together**: agree on the KPI dashboard (triage time, escalation rate, SLA credits) and review it at week 4.

Repository, notebooks with outputs, and evidence: see `README.md` and `evidence/`.

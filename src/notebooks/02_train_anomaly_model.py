# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: -all
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.6
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # 02 · Client anomaly model — train, register in Unity Catalog, batch score
#
# **Question for support:** *which client / site / app is degraded right now, before the
# client opens a ticket?*
#
# * Features come from `gold_client_health` (5-minute windows per client × site × service):
#   error rate, warn rate, and p50/p95 latency relative to the service's normal latency.
# * Model: scikit-learn `IsolationForest` inside a `Pipeline` (unsupervised; no labels needed
#   in production).
# * Evaluation: the synthetic generator injects three known incidents
#   (`src/config/incidents.json`), which act as ground truth for precision / recall.
# * The model is logged to MLflow, registered as `<catalog>.<schema>.client_anomaly_model`
#   with alias `champion`, then loaded back by alias to score every window into
#   `gold_client_anomalies`.

# %%
import importlib.util
import subprocess
import sys

for pkg, mod in [("scikit-learn", "sklearn"), ("mlflow>=3", "mlflow")]:
    if importlib.util.find_spec(mod) is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

# %%
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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

    PROFILE = os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai")
    spark = DatabricksSession.builder.profile(PROFILE).serverless().getOrCreate()
    os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", PROFILE)
    mlflow.set_tracking_uri(f"databricks://{PROFILE}")
    mlflow.set_registry_uri(f"databricks-uc://{PROFILE}")
else:
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")

CATALOG = param("catalog", "accessdemo")
SCHEMA = param("schema", "dev_jesus_zaragoza_helix_support")
EXPERIMENT = param("experiment", "") or (
    f"/Users/{spark.sql('SELECT current_user()').first()[0]}/helix_client_anomaly_model")
MODEL_NAME = f"{CATALOG}.{SCHEMA}.client_anomaly_model"
FEATURES = ["error_rate", "warn_rate", "p95_ratio", "p50_ratio"]
print(f"model={MODEL_NAME} experiment={EXPERIMENT}")

# %% [markdown]
# ## Load features from the gold layer

# %%
health = spark.sql(f"""
  WITH h AS (SELECT * FROM {CATALOG}.{SCHEMA}.gold_client_health WHERE event_count >= 10),
  base AS (
    SELECT service_name,
           percentile_approx(p95_latency_ms, 0.5) AS svc_p95_median,
           percentile_approx(p50_latency_ms, 0.5) AS svc_p50_median
    FROM h GROUP BY service_name
  )
  SELECT h.*,
         h.p95_latency_ms / b.svc_p95_median AS p95_ratio,
         h.p50_latency_ms / b.svc_p50_median AS p50_ratio
  FROM h JOIN base b USING (service_name)
""").toPandas()
health["window_start"] = pd.to_datetime(health["window_start"], utc=True)
print(f"{len(health):,} client-site-service windows; "
      f"{health.client_id.nunique()} clients, {health.site_id.nunique()} sites, "
      f"{health.service_name.nunique()} services")
print(health[FEATURES].describe().round(3).to_string())

# %% [markdown]
# ## Ground truth from the injected incidents (evaluation only — never a feature)

# %%
incidents = json.loads((Path.cwd().parent / "config" / "incidents.json").read_text())["incidents"]
sim_start = health["window_start"].min()
hour = (health["window_start"] - sim_start).dt.total_seconds() / 3600


def label_row(i: int) -> str | None:
    r = health.iloc[i]
    for inc in incidents:
        if (inc["start_hour"] <= hour.iloc[i] < inc["end_hour"]
                and r.client_id == inc["client_id"]
                and r.service_name in inc["services"]
                and (not inc["site_ids"] or r.site_id in inc["site_ids"])):
            return inc["incident_key"]
    return None


health["true_incident"] = [label_row(i) for i in range(len(health))]
y_true = health["true_incident"].notna().astype(int)
print(f"simulated timeline starts {sim_start}; labelled incident windows: {y_true.sum()} "
      f"of {len(health):,} ({y_true.mean():.2%})")
print(health.loc[y_true == 1].groupby("true_incident").size().to_string())

# %% [markdown]
# ## Train and log to MLflow

# %%
mlflow.set_experiment(EXPERIMENT)
params = {"n_estimators": 300, "contamination": 0.005, "max_samples": 4096, "random_state": 7}
X = health[FEATURES].astype("float64")

with mlflow.start_run(run_name=f"isoforest_{datetime.now(timezone.utc):%Y%m%dT%H%M}") as run:
    model = Pipeline([("scale", StandardScaler()), ("iforest", IsolationForest(**params))])
    model.fit(X)
    flagged = (model.predict(X) == -1).astype(int)
    score = -model.score_samples(X)  # higher = more anomalous

    metrics = {
        "precision": precision_score(y_true, flagged),
        "recall": recall_score(y_true, flagged),
        "roc_auc": roc_auc_score(y_true, score),
        "average_precision": average_precision_score(y_true, score),
        "flagged_windows": int(flagged.sum()),
        "training_windows": int(len(X)),
    }
    mlflow.log_params(params | {"features": ",".join(FEATURES)})
    mlflow.log_metrics(metrics)
    mlflow.sklearn.log_model(
        model,
        name="model",
        signature=infer_signature(X, model.predict(X)),
        input_example=X.head(3),
        registered_model_name=MODEL_NAME,
    )
    run_id = run.info.run_id

print(f"MLflow run {run_id}")
for k, v in metrics.items():
    print(f"  {k:18s} {v:.4f}" if isinstance(v, float) else f"  {k:18s} {v}")

recall_by_incident = (
    pd.DataFrame({"incident": health["true_incident"], "flagged": flagged})
    .dropna().groupby("incident")["flagged"].agg(["sum", "count"])
)
recall_by_incident["recall"] = (recall_by_incident["sum"] / recall_by_incident["count"]).round(3)
print("\nRecall per injected incident:")
print(recall_by_incident.to_string())

# %% [markdown]
# ## Promote to `champion` in Unity Catalog

# %%
client = mlflow.MlflowClient()
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'") if v.run_id == run_id)
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description=(
    "IsolationForest over 5-minute client health windows (error rate, warn rate, latency "
    "ratios). Flags degraded client/site/service windows for Helix support triage."))
print(f"{MODEL_NAME} version {version} -> alias 'champion'")

# %% [markdown]
# ## Batch score with the registered model → `gold_client_anomalies`

# %%
champion = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
health["is_anomaly"] = champion.predict(X) == -1
health["anomaly_score"] = score.round(4)
health["model_version"] = int(version)
health["scored_at"] = datetime.now(timezone.utc)

out_cols = ["health_key", "window_start", "client_id", "client_name", "site_id", "service_name",
            "event_count", "error_count", "warn_count", "error_rate", "warn_rate",
            "p50_latency_ms", "p95_latency_ms", "p95_ratio", "top_error_signature",
            "anomaly_score", "is_anomaly", "model_version", "scored_at"]
anoms = health.loc[health["is_anomaly"], out_cols].sort_values("anomaly_score", ascending=False)
(spark.createDataFrame(anoms)
    .write.mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.gold_client_anomalies"))
spark.sql(f"""COMMENT ON TABLE {CATALOG}.{SCHEMA}.gold_client_anomalies IS
  'Client/site/service 5-minute windows flagged by {MODEL_NAME}@champion (v{version}).'""")
print(f"wrote {len(anoms)} anomalous windows to {CATALOG}.{SCHEMA}.gold_client_anomalies")
print(anoms.head(15)[["window_start", "client_id", "site_id", "service_name", "error_rate",
                      "p95_latency_ms", "top_error_signature", "anomaly_score"]].to_string(index=False))

# %%
result = {"run_id": run_id, "model": MODEL_NAME, "version": int(version),
          "anomalies": int(len(anoms)), **{k: round(float(v), 4) for k, v in metrics.items()}}
print(json.dumps(result, indent=2))
if IN_DATABRICKS:
    dbutils.notebook.exit(json.dumps(result))  # noqa: F821

# Notebook stdout: `src/notebooks/02_train_anomaly_model.ipynb`

## Cell 3

```
model=accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model experiment=/Users/<user>/helix_client_anomaly_model
```

## Cell 5

```
26,000 client-site-service windows; 5 clients, 15 sites, 6 services
       error_rate  warn_rate  p95_ratio  p50_ratio
count   26000.000  26000.000  26000.000  26000.000
mean        0.016      0.050      1.026      1.012
std         0.022      0.032      0.255      0.220
min         0.000      0.000      0.540      0.678
25%         0.000      0.028      0.920      0.949
50%         0.013      0.047      1.000      1.000
75%         0.025      0.069      1.095      1.054
max         0.446      0.490      8.387      6.834
```

## Cell 7

```
simulated timeline starts 2026-11-02 00:10:00+00:00; labelled incident windows: 69 of 26,000 (0.27%)
true_incident
INC-ARCHIVE-SLOW-101     6
INC-ESIGN-503           27
INC-UPLOAD-204          36
```

## Cell 9

```
[1;38;5;208mIf you are using MLflow Tracing, you can migrate your traces to Unity Catalog for unlimited storage, fine-grained access controls, and queryability from notebooks, SQL, and dashboards. [94mLearn more: https://docs.databricks.com/aws/en/mlflow3/genai/tracing/migrate-traces-to-uc[0m
🔗 View Logged Model at: https://fevm-serverless-stable-2xts9s.cloud.databricks.com/ml/experiments/474499328285340/models/m-36c9cc7378fd4bd5a9ee74076b5eab1f
2026/11/02 17:19:46 WARNING mlflow.sklearn: Saving scikit-learn models in the pickle or cloudpickle format requires exercising caution because these formats rely on Python's object serialization mechanism, which can execute arbitrary code during deserialization. The recommended safe alternative is the 'skops' format. For more information, see: https://scikit-learn.org/stable/model_persistence.html
2026/11/02 17:19:48 WARNING mlflow.utils.environment: Failed to resolve installed pip version. ``pip`` will be added to conda.yaml environment spec without a version specifier.
Registered model 'accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model' already exists. Creating a new version of this model...
🔗 Created version '4' of model 'accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model': https://fevm-serverless-stable-2xts9s.cloud.databricks.com/explore/data/models/accessdemo/dev_jesus_zaragoza_helix_support/client_anomaly_model/version/4
🏃 View run isoforest_20261103T0119 at: https://fevm-serverless-stable-2xts9s.cloud.databricks.com/ml/experiments/474499328285340/runs/eead63019777404e803eb480989c5a9d
🧪 View experiment at: https://fevm-serverless-stable-2xts9s.cloud.databricks.com/ml/experiments/474499328285340
MLflow run eead63019777404e803eb480989c5a9d
  precision          0.5308
  recall             1.0000
  roc_auc            0.9999
  average_precision  0.9500
  flagged_windows    130
  training_windows   26000
Recall per injected incident:
                      sum  count  recall
incident                                
INC-ARCHIVE-SLOW-101    6      6     1.0
INC-ESIGN-503          27     27     1.0
INC-UPLOAD-204         36     36     1.0
```

## Cell 11

```
accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model version 4 -> alias 'champion'
```

## Cell 13

```
wrote 130 anomalous windows to accessdemo.dev_jesus_zaragoza_helix_support.gold_client_anomalies
             window_start     client_id  site_id     service_name  error_rate  p95_latency_ms      top_error_signature  anomaly_score
2026-11-02 03:30:00+00:00 northwind-bio site-101  imaging-archive      0.0208          1935.1              S3 put slow         0.8465
2026-11-02 03:25:00+00:00 northwind-bio site-101  imaging-archive      0.0465          1800.7              S3 put slow         0.8435
2026-11-02 03:15:00+00:00 northwind-bio site-101  imaging-archive      0.0435          2272.5              S3 put slow         0.8420
2026-11-02 03:20:00+00:00 northwind-bio site-101  imaging-archive      0.0366          1674.0              S3 put slow         0.8409
2026-11-02 03:35:00+00:00 northwind-bio site-101  imaging-archive      0.0444          1786.0              S3 put slow         0.8376
2026-11-02 18:40:00+00:00  fabrikam-cro site-204     dicom-router      0.2203          1386.2        association retry         0.8350
2026-11-02 18:55:00+00:00  fabrikam-cro site-204     dicom-router      0.3864           997.3           upload timeout         0.8339
2026-11-02 17:50:00+00:00  fabrikam-cro site-204     dicom-router      0.1905          1177.1        association retry         0.8296
2026-11-02 18:10:00+00:00  fabrikam-cro site-204 trial-upload-api      0.2273          2471.4        slow upload chunk         0.8270
2026-11-02 18:05:00+00:00  fabrikam-cro site-204     dicom-router      0.3148          1161.9        association retry         0.8244
2026-11-02 19:05:00+00:00  fabrikam-cro site-204     dicom-router      0.2414          1103.7        association retry         0.8236
2026-11-02 18:50:00+00:00  fabrikam-cro site-204     dicom-router      0.2500          1557.4        association retry         0.8233
2026-11-02 19:00:00+00:00  fabrikam-cro site-204 trial-upload-api      0.4459          2729.8           upload timeout         0.8233
2026-11-02 09:45:00+00:00    contoso-tx site-113     econsent-web      0.4043          1048.7 e-signature provider 503         0.8228
2026-11-02 03:40:00+00:00 northwind-bio site-101  imaging-archive      0.0108          1752.9              S3 put slow         0.8224
```

## Cell 14

```
{
  "run_id": "eead63019777404e803eb480989c5a9d",
  "model": "accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model",
  "version": 4,
  "anomalies": 130,
  "precision": 0.5308,
  "recall": 1.0,
  "roc_auc": 0.9999,
  "average_precision": 0.95,
  "flagged_windows": 130.0,
  "training_windows": 26000.0
}
```


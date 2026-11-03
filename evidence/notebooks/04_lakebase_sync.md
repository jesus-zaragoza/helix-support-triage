# Notebook stdout: `src/notebooks/04_lakebase_sync.ipynb`

## Cell 3

```
source=accessdemo.dev_jesus_zaragoza_helix_support branch=projects/helix-support/branches/production db=databricks_postgres
```

## Cell 4

```
REFRESH accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_health (pipeline ab33e67c-81bc-41ff-a828-93627370ca4e)
REFRESH accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_anomalies (pipeline 63e030b2-129b-45d7-ad2c-4522430c766a)
REFRESH accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_incident_briefs (pipeline 268980c5-cda9-4c9b-869d-19cc10eb8d87)
```

## Cell 5

```
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_health: COMPLETED
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_anomalies: COMPLETED
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_incident_briefs: COMPLETED
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_health: state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE last_sync=None message=Synced table creation succeeded using Delta Live Tables: https://fevm-serverless-stable-2xts9s.cloud.databricks.com#joblist/pipelines/ab33e67c-81bc-41ff-a828-93627370ca4e/updates/01c09665-030e-455c-999c-7b5041ef39c2.
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_anomalies: state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE last_sync=None message=Synced table creation succeeded using Delta Live Tables: https://fevm-serverless-stable-2xts9s.cloud.databricks.com#joblist/pipelines/63e030b2-129b-45d7-ad2c-4522430c766a/updates/a238339c-e92c-419a-bcde-64d94d11b517.
accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_incident_briefs: state=SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE last_sync=None message=Synced table creation succeeded using Delta Live Tables: https://fevm-serverless-stable-2xts9s.cloud.databricks.com#joblist/pipelines/268980c5-cda9-4c9b-869d-19cc10eb8d87/updates/aff96612-43b1-40bf-99b4-abe292a718d2.
```


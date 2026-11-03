# Notebook stdout: `src/notebooks/01_governance.ipynb`

## Cell 2

```
catalog=accessdemo schema=dev_jesus_zaragoza_helix_support bronze=accessdemo.fluentbit.helix_otel_logs phase=all app_sp=set
```

## Cell 4

```
OK   CREATE SCHEMA IF NOT EXISTS accessdemo.dev_jesus_zaragoza_helix_support
OK   CREATE OR REPLACE FUNCTION accessdemo.dev_jesus_zaragoza_helix_support.mask_email(email STRING)
OK   CREATE OR REPLACE FUNCTION accessdemo.dev_jesus_zaragoza_helix_support.mask_study_id(study_id STRING)
OK   CREATE OR REPLACE FUNCTION accessdemo.dev_jesus_zaragoza_helix_support.client_isolation_filter(client_id STRIN
```

## Cell 6

```
OK   COMMENT ON SCHEMA accessdemo.dev_jesus_zaragoza_helix_support IS 'Helix Clinical Cloud support triage: typed a
OK   ALTER SCHEMA accessdemo.dev_jesus_zaragoza_helix_support SET TAGS ('domain' = 'operations', 'data_classificati
OK   ALTER TABLE accessdemo.fluentbit.helix_otel_logs SET TAGS ('domain' = 'operations', 'layer' = 'bronze', 'conta
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs SET TAGS ('domain' = 'operations', 'l
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs ALTER COLUMN user_email SET TAGS ('pi
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs ALTER COLUMN study_id SET TAGS ('conf
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health SET TAGS ('domain' = 'operations',
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_summary SET TAGS ('domain' = 'operations
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_error_signatures SET TAGS ('domain' = 'operations
OK   ALTER TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_service_volume SET TAGS ('domain' = 'operations',
OK   GRANT USE SCHEMA ON SCHEMA accessdemo.dev_jesus_zaragoza_helix_support TO `account users`
OK   GRANT SELECT ON TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health TO `account users`
OK   GRANT SELECT ON TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_summary TO `account users`
OK   GRANT SELECT ON TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_error_signatures TO `account users`
OK   GRANT SELECT ON TABLE accessdemo.dev_jesus_zaragoza_helix_support.gold_service_volume TO `account users`
OK   GRANT USE CATALOG ON CATALOG accessdemo TO `<app-sp>`
OK   GRANT USE SCHEMA ON SCHEMA accessdemo.dev_jesus_zaragoza_helix_support TO `<app-sp>
OK   GRANT SELECT ON SCHEMA accessdemo.dev_jesus_zaragoza_helix_support TO `<app-sp>`
```

## Cell 8

```
== Column masks and row filters bound to silver ==
     policy column_name                                                       function_name
column_mask    study_id           accessdemo.dev_jesus_zaragoza_helix_support.mask_study_id
column_mask  user_email              accessdemo.dev_jesus_zaragoza_helix_support.mask_email
 row_filter   client_id accessdemo.dev_jesus_zaragoza_helix_support.client_isolation_filter
== Table tags ==
           table_name     tag_name  tag_value
   gold_client_health contains_pii      false
   gold_client_health       domain operations
   gold_client_health        layer       gold
   gold_client_health      serving   lakebase
gold_error_signatures contains_pii      false
gold_error_signatures       domain operations
gold_error_signatures        layer       gold
gold_incident_summary contains_pii      false
gold_incident_summary       domain operations
gold_incident_summary        layer       gold
  gold_service_volume contains_pii      false
  gold_service_volume       domain operations
  gold_service_volume        layer       gold
     silver_otel_logs contains_pii       true
     silver_otel_logs       domain operations
     silver_otel_logs        layer     silver
== Column tags ==
      table_name column_name        tag_name           tag_value
silver_otel_logs    study_id confidentiality client_confidential
silver_otel_logs  user_email    pii_category               email
== Grants made on this schema and its tables (inherited catalog grants omitted) ==
                             grantee privilege_type object_type                      object_name
<app-sp>         SELECT      SCHEMA dev_jesus_zaragoza_helix_support
<app-sp>     USE_SCHEMA      SCHEMA dev_jesus_zaragoza_helix_support
                       account users     USE_SCHEMA      SCHEMA dev_jesus_zaragoza_helix_support
                       account users         SELECT       TABLE               gold_client_health
                       account users         SELECT       TABLE            gold_error_signatures
                       account users         SELECT       TABLE            gold_incident_summary
                       account users         SELECT       TABLE              gold_service_volume
```

## Cell 9

```
== Masked read of silver (caller is not in helix_support_analysts) ==
   client_id  site_id study_id               user_email     service_name severity_text
 adatum-clin site-501  ADC-***  ***@adatum-clin.example trial-upload-api          INFO
fabrikam-cro site-202  FAB-*** ***@fabrikam-cro.example  imaging-archive          INFO
tailspin-onc site-301  TSO-*** ***@tailspin-onc.example  imaging-archive          WARN
 adatum-clin site-502  ADC-***  ***@adatum-clin.example  imaging-archive          INFO
  contoso-tx site-112  CTX-***   ***@contoso-tx.example  imaging-archive          INFO
== Row filter: isolated tenant wingtip-gx is in bronze but hidden in silver ==
 layer  wingtip_rows
bronze        196288
silver             0
```

## Cell 10

```
== Lineage captured by Unity Catalog (system.access.table_lineage) ==
                                           source_table_full_name                                               target_table_full_name entity_type               last_seen
     accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs       accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health    PIPELINE 2026-11-03 00:27:07.076
     accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs    accessdemo.dev_jesus_zaragoza_helix_support.gold_error_signatures    PIPELINE 2026-11-03 00:27:05.755
accessdemo.dev_jesus_zaragoza_helix_support.gold_client_anomalies     accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_briefs         JOB 2026-11-03 00:34:38.058
     accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs     accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_briefs         JOB 2026-11-03 00:34:38.058
     accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs    accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_summary    PIPELINE 2026-11-03 00:27:05.813
     accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs      accessdemo.dev_jesus_zaragoza_helix_support.gold_service_volume    PIPELINE 2026-11-03 00:27:05.668
accessdemo.dev_jesus_zaragoza_helix_support.gold_client_anomalies accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_anomalies    PIPELINE 2026-11-03 00:41:53.944
   accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health    accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_client_health    PIPELINE 2026-11-03 00:41:43.386
 accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_briefs  accessdemo.dev_jesus_zaragoza_helix_support.lb_gold_incident_briefs    PIPELINE 2026-11-03 00:42:05.325
                             accessdemo.fluentbit.helix_otel_logs         accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs    PIPELINE 2026-11-03 00:26:57.062
```


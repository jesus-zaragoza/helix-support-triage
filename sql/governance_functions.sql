-- Unity Catalog governance functions used by the silver table definition
-- (column masks + row filter are declared in silver_otel_logs.py).
-- Placeholders ${catalog} / ${schema} are substituted by src/notebooks/01_governance.ipynb.

CREATE SCHEMA IF NOT EXISTS ${catalog}.${schema};

-- PII: site-coordinator email. Support analysts see it; everyone else sees only the domain.
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.mask_email(email STRING)
RETURNS STRING
COMMENT 'Column mask: full email for helix_support_analysts, otherwise ***@domain'
RETURN CASE
  WHEN is_account_group_member('helix_support_analysts') THEN email
  ELSE regexp_replace(email, '^[^@]+', '***')
END;

-- Client-confidential: study protocol id. Keep the client prefix, hide the protocol.
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.mask_study_id(study_id STRING)
RETURNS STRING
COMMENT 'Column mask: full study id for helix_support_analysts, otherwise client prefix only'
RETURN CASE
  WHEN is_account_group_member('helix_support_analysts') THEN study_id
  ELSE concat(split_part(study_id, '-', 1), '-***')
END;

-- Tenant isolation: Wingtip Genomics has a contractual data-isolation clause, so its
-- events are only visible to its dedicated support pod.
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.client_isolation_filter(client_id STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: hide isolated tenants (wingtip-gx) unless the caller is in helix_wingtip_pod'
RETURN client_id <> 'wingtip-gx' OR is_account_group_member('helix_wingtip_pod');

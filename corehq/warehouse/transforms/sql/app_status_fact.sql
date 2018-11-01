-- Update Form Info
INSERT INTO {{ app_status_fact }} (
       last_form_submission_date,
       last_form_app_build_version,
       last_form_app_commcare_version,
       user_dim_id,
       app_dim_id,
       domain,
       batch_id
)

SELECT 
       last_submission,
       submission_build_version,
       commcare_version,
       user_dim_id,
       app_dim_id,
       domain,
       '{{ batch_id }}'

FROM
    {{ app_status_form_staging }} as form_table
ON CONFLICT (app_dim_id, user_dim_id) DO UPDATE
SET last_form_submission_date = EXCLUDED.last_form_submission_date,
    last_form_app_build_version = EXCLUDED.last_form_app_build_version,
    last_form_app_commcare_version = EXCLUDED.last_form_app_commcare_version,
    domain = EXCLUDED.domain,
    batch_id = EXCLUDED.batch_id;

-- Update Synclog Info
INSERT INTO {{ app_status_fact }} (
       user_dim_id,
       last_sync_log_date,
       domain,
       app_dim_id,
       batch_id
)

SELECT
       sync_table.user_dim_id,
       sync_table.last_sync,
       sync_table.domain,
       app_status.app_dim_id,
       '{{ batch_id }}'
FROM
    {{ app_status_synclog_staging }} as sync_table
LEFT JOIN {{ app_status_fact }} as app_status
ON app_status.user_dim_id=sync_table.user_dim_id
ON CONFLICT (user_dim_id, COALESCE(app_dim_id, -1)) DO UPDATE
SET last_sync_log_date = EXCLUDED.last_sync_log_date,
    domain = EXCLUDED.domain,
    batch_id = EXCLUDED.batch_id;

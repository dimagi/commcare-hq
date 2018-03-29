INSERT INTO {{ app_status_fact }} (
       last_form_submission_date,
       last_form_app_build_version,
       last_form_app_commcare_version,
       user_dim_id,
       app_dim_id,
       domain,
       last_sync_log_date,
       batch_id
)

SELECT 
       form_table.last_submission,
       form_table.submission_build_version,
       form_table.commcare_version,
       form_table.user_dim_id,
       form_table.app_dim_id,
       form_table.domain,
       sync_table.last_sync,
       sync_table.sync_build_version,
       '{{ batch_id }}'

FROM
    {{ app_status_form_staging }} as form_table
    LEFT JOIN {{ app_status_synclog_staging }} as sync_table
    ON form_table.user_dim_id = sync_table.user_dim_id
ON CONFLICT (app_dim_id, user_dim_id) DO UPDATE
SET last_form_submission_date = EXCLUDED.last_form_submission_date,
    last_form_app_build_version = EXCLUDED.last_form_app_build_version,
    last_form_app_commcare_version = EXCLUDED.last_form_app_commcare_version,
    user_dim_id = EXCLUDED.user_dim_id,
    app_dim_id = EXCLUDED.app_dim_id,
    domain = EXCLUDED.domain,
    last_sync_log_date = EXCLUDED.last_sync_log_date,
    batch_id = EXCLUDED.batch_id;

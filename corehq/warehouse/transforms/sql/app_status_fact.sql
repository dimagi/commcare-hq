INSERT INTO {{ app_status_fact }} (
       last_form_submission_date,
       last_form_app_build_version,
       last_form_app_commcare_version,
       user_id,
       app_id,
       domain,
       last_sync_log_date,
       last_sync_log_app_build_version,
       batch_id
)

SELECT 
       form_table.last_submission,
       form_table.submission_build_version,
       form_table.commcare_version,
       form_table.user_id,
       form_table.app_id,
       form_table.domain,
       sync_table.last_sync,
       sync_table.sync_build_version,
       '{{ batch_id }}'

FROM
    {{ app_status_form_staging }} as form_table
    LEFT JOIN {{ app_status_synclog_staging }} as sync_table
    ON form_table.user_id = sync_table.user_id
ON CONFLICT (app_id, user_id) DO UPDATE
SET last_form_submission_date = EXCLUDED.last_form_submission_date,
    last_form_app_build_version = EXCLUDED.last_form_app_build_version,
    last_form_app_commcare_version = EXCLUDED.last_form_app_commcare_version,
    user_id = EXCLUDED.user_id,
    app_id = EXCLUDED.app_id,
    domain = EXCLUDED.domain,
    last_sync_log_date = EXCLUDED.last_sync_log_date,
    last_sync_log_app_build_version = EXCLUDED.last_sync_log_app_build_version,
    batch_id = EXCLUDED.batch_id;

INSERT INTO {{ synclog_fact }} (
    sync_log_id,
    sync_date,
    domain,
    domain_dim_id,
    user_dim_id,
    build_id,
    duration,
    batch_id
)
SELECT
    synclog_table.sync_log_id,
    synclog_table.sync_date,
    domain_table.domain,
    domain_table.id,
    user_table.id,
    synclog_table.build_id,
    synclog_table.duration,
    '{{ batch_id }}'
FROM
    {{ synclog_staging }} AS synclog_table
LEFT JOIN {{ domain_dim }} AS domain_table ON synclog_table.domain = domain_table.domain
LEFT JOIN {{ user_dim }} AS user_table ON synclog_table.user_id = user_table.user_id
LEFT JOIN {{ synclog_fact }} AS synclog_fact ON user_table.id = synclog_fact.user_dim_id
WHERE synclog_table.sync_date > synclog_fact.sync_date OR synclog_fact.sync_date IS NULL

ON CONFLICT (user_dim_id) DO UPDATE
SET sync_log_id = EXCLUDED.sync_log_id,
    sync_date = EXCLUDED.sync_date,
    domain = EXCLUDED.domain,
    domain_dim_id = EXCLUDED.domain_dim_id,
    build_id = EXCLUDED.build_id,
    duration = EXCLUDED.duration,
    batch_id = EXCLUDED.batch_id;

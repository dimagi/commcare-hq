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
    sync_log_id,
    sync_date,
    domain,
    domain_dim_id,
    user_dim_id,
    build_id,
    duration,
    '{{ batch_id }}'
FROM
(
SELECT
    row_number() over wnd,
    synclog_table.sync_log_id as sync_log_id,
    synclog_table.sync_date as sync_date,
    domain_table.domain as domain,
    domain_table.id as domain_dim_id,
    user_table.id as user_dim_id,
    synclog_table.build_id as build_id,
    synclog_table.duration as duration
FROM
    {{ synclog_staging }} AS synclog_table
LEFT JOIN {{ domain_dim }} AS domain_table ON synclog_table.domain = domain_table.domain
LEFT JOIN {{ user_dim }} AS user_table ON synclog_table.user_id = user_table.user_id
LEFT JOIN {{ synclog_fact }} AS synclog_fact ON user_table.id = synclog_fact.user_dim_id
WHERE
    (synclog_table.sync_date > synclog_fact.sync_date OR synclog_fact.sync_date IS NULL)
    AND user_table.id IS NOT NULL
WINDOW wnd AS (
       PARTITION BY user_table.id ORDER BY synclog_table.sync_date AT TIME ZONE 'UTC' DESC
       ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
) as sync_data where row_number=1
ON CONFLICT (user_dim_id) DO UPDATE
SET sync_log_id = EXCLUDED.sync_log_id,
    sync_date = EXCLUDED.sync_date,
    domain = EXCLUDED.domain,
    domain_dim_id = EXCLUDED.domain_dim_id,
    build_id = EXCLUDED.build_id,
    duration = EXCLUDED.duration,
    batch_id = EXCLUDED.batch_id;

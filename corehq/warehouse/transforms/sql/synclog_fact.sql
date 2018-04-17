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
    domain_table.domain,
    domain_table.id,
    user_table.id,
    build_id,
    duration,
    '{{ batch_id }}'
FROM
    {{ synclog_staging }} AS synclog_table
LEFT JOIN {{ domain_dim }} AS domain_table ON synclog_table.domain = domain_table.domain
LEFT JOIN {{ user_dim }} AS user_table ON synclog_table.user_id = user_table.user_id

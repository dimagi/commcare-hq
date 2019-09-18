INSERT INTO {{ app_status_synclog_staging }} (
       last_sync,
       user_dim_id,
       domain,
       batch_id
)
SELECT
    last_sync,
    user_dim_id,
    domain,
    '{{ batch_id }}'
FROM
(
    SELECT
        row_number() over wnd,
        CASE
            WHEN sync_date < app_status.last_sync_log_date
            THEN app_status.last_sync_log_date
            ELSE sync_date
        END AS last_sync,
        sync_fact.user_dim_id as user_dim_id,
        sync_fact.domain as domain
    FROM {{ synclog_fact }} as sync_fact
	    LEFT JOIN {{ app_status_fact }} as app_status
	    ON sync_fact.user_dim_id = app_status.user_dim_id
    WINDOW wnd AS (
        PARTITION BY sync_fact.user_dim_id
        ORDER BY sync_date AT TIME ZONE 'UTC' DESC, app_status.last_sync_log_date AT TIME ZONE 'UTC' DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)
) as sync_data where row_number=1;

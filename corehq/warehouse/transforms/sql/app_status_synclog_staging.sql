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
	user_dim.id as user_dim_id,
	sync_staging.domain as domain
        FROM {{ synclog_staging }} as sync_staging
	LEFT JOIN {{ user_dim }} as user_dim
	ON sync_staging.user_id = user_dim.user_id
	LEFT JOIN {{ app_status_fact }} as app_status
	ON user_dim.id = app_status.user_dim_id
        WINDOW wnd AS (
            PARTITION BY sync_staging.user_id ORDER BY sync_date AT TIME ZONE 'UTC' DESC, app_status.last_sync_log_date AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)
) as sync_data where row_number=1;

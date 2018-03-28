INSERT INTO {{ app_status_synclog_staging }} (
       last_sync,
       sync_build_version,
       user_id,
       domain,
       batch_id
)
SELECT
    last_sync,
    sync_build_version,
    user_id,
    domain,
    '{{ batch_id }}'
FROM
(
SELECT
	row_number() over wnd,
	CASE
	    WHEN sync_date < app_status.last_sync_log_date
	    THEN app_status.last_sync_log_date
	    ELSE first_value(sync_date AT TIME ZONE 'UTC') OVER wnd
	END AS last_sync,
	CASE
	WHEN sync_date < app_status.last_sync_log_date
	THEN app_status.last_sync_log_app_build_version
        ELSE app_dim.version::VARCHAR
	END as sync_build_version,
	sync_staging.user_id as user_id,
	sync_staging.domain as domain
        FROM {{ synclog_staging }} as sync_staging
	LEFT JOIN {{ app_status_fact }} as app_status
	ON sync_staging.user_id = app_status.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON sync_staging.build_id = app_dim.application_id
        WINDOW wnd AS (
            PARTITION BY sync_staging.user_id ORDER BY sync_date AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)
) as sync_data where row_number=1;

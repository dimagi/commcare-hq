INSERT INTO {{ app_status_synclog_staging }} (
       last_sync,
       sync_build_version,
       user_dim_id,
       domain_dim_id
)

SELECT
	CASE
	    WHEN first_value(sync_date AT TIME ZONE 'UTC') OVER wnd < first_value(app_status.last_sync_log_date  AT TIME ZONE 'UTC') over WND
	    THEN first_value(app_status.last_sync_log_date) over WND
	    ELSE first_value(sync_date AT TIME ZONE 'UTC') OVER wnd
	END AS last_sync,
             first_value(sync_staging.user_id) OVER wnd AS user_id,
	CASE
	WHEN first_value(sync_date AT TIME ZONE 'UTC') OVER wnd < first_value(app_status.last_sync_log_date  AT TIME ZONE 'UTC') over WND
	THEN first_value(app_status.last_sync_log_app_build_version) OVER WND
        ELSE first_value(app_dim.version::VARCHAR) OVER wnd
	END as sync_build_version,
	user_dim.id,
	domain_dim.id
        FROM {{ synclog_staging }} as sync_staging
	LEFT JOIN {{ app_status_fact }} as app_status
	ON sync_staging.user_id = app_status.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON sync_staging.build_id = app_dim.application_id
	LEFT JOIN {{ user_dim }} as user_dim
	ON user_dim.user_id = sync_staging.user_id
	LEFT JOIN {{ domain_dim }} as domain_dim
	ON sync_staging.domain = domain_dim.domain
        WINDOW wnd AS (
            PARTITION BY sync_staging.user_id ORDER BY sync_date AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	);

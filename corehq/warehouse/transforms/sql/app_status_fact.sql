INSERT INTO {{ app_status_fact }} (
       last_form_submission_date,
       last_form_app_build_version,
       last_form_app_commcare_version,
       user_dim_id,
       app_dim_id,
       domain_dim_id,
       last_sync_log_date,
       last_sync_log_app_build_version
)
SELECT 
       form_table.last_submission,
       form_table.submission_build_version,
       form_table.commcare_version,
       user_dim.id,
       form_table.app_dim_id,
       form_table.domain_dim_id,
       sync_table.last_sync,
       sync_table.sync_build_version

FROM
(
        (SELECT
	CASE
	    WHEN first_value(received_on AT TIME ZONE 'UTC') OVER wnd < first_value(app_status.last_form_submission_date  AT TIME ZONE 'UTC') over WND
	    THEN first_value(app_status.last_form_submission_date) over WND
	    ELSE  first_value(received_on AT TIME ZONE 'UTC') OVER wnd
	END AS last_submission,
	CASE
	    WHEN first_value(received_on AT TIME ZONE 'UTC') OVER wnd < first_value(app_status.last_form_submission_date  AT TIME ZONE 'UTC') over WND
	    THEN first_value(app_status.last_form_app_build_version) OVER wnd
            ELSE first_value(app_dim.version::VARCHAR) OVER wnd
	END AS submission_build_version,
	CASE
	    WHEN first_value(received_on AT TIME ZONE 'UTC') OVER wnd < first_value(app_status.last_form_submission_date  AT TIME ZONE 'UTC') over WND
	    THEN first_value(app_status.last_form_app_commcare_version) OVER wnd
	    ELSE first_value(commcare_version) OVER wnd
	END AS commcare_version,
	    first_value(app_dim_id) OVER wnd as app_dim_id,
	    first_value(domain_dim.id) OVER wnd as domain_dim_id,
	    first_value(form_staging.user_id) OVER wnd as user_id
        FROM {{ form_staging }} as form_staging
	LEFT JOIN {{ app_status_fact }} as app_status
	ON form_staging.app_id = app_status.app_id and form_staging.user_id = app_status.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON form_staging.build_id = app_dim.application_id
	LEFT JOIN {{ domain_dim }} as domain_dim
	ON form_staging.domain = domain_dim.domain
        WINDOW wnd AS (
            PARTITION BY form_staging.user_id, form_staging.app_id ORDER BY received_on AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)) as form_table

	LEFT JOIN
	(
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
	END as sync_build_version
        FROM {{ synclog_staging }} as sync_staging
	LEFT JOIN {{ app_status_fact }} as app_status
	ON sync_staging.user_id = app_status.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON sync_staging.build_id = app_dim.application_id
        WINDOW wnd AS (
            PARTITION BY sync_staging.user_id ORDER BY sync_date AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	) 
	) as sync_table
	ON sync_table.user_id = form_table.user_id
	LEFT JOIN {{ user_dim }} as user_dim
	ON user_dim.user_id = form_table.user_id
)
ON CONFLICT (app_id, user_id) DO UPDATE
SET last_form_submission_date = EXCLUDED.last_form_submission_date,
    last_form_app_build_version = EXCLUDED.last_form_app_build_version,
    last_form_app_commcare_version = EXCLUDED.last_form_app_commcare_version,
    user_dim_id = EXCLUDED.user_dim_id,
    app_dim_id = EXCLUDED.app_dim_id,
    domain_dim_id = EXCLUDED.domain_dim_id,
    last_sync_log_date = EXCLUDED.last_sync_log_date,
    last_sync_log_app_build_version = EXCLUDED.last_sync_log_app_build_version;

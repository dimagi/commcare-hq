INSERT INTO {{ app_status_form_staging }} (
       last_submission,
       submission_build_version,
       commcare_version,
       user_dim_id,
       app_dim_id,
       domain_dim_id,
)

SELECT
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
	    first_value(form_staging.user_id) OVER wnd as user_id,
	user_dim.id,
	app_dim.id,
	domain_dim.id
        FROM {{ form_staging }} as form_staging
	LEFT JOIN {{ app_status_fact }} as app_status
	ON form_staging.app_id = app_status.app_id and form_staging.user_id = app_status.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON form_staging.build_id = app_dim.application_id
	LEFT JOIN {{ domain_dim }} as domain_dim
	ON form_staging.domain = domain_dim.domain
	LEFT JOIN {{ user_dim }} as user_dim
	ON user_dim.user_id = form_staging.user_id
        WINDOW wnd AS (
            PARTITION BY form_staging.user_id, form_staging.app_id ORDER BY received_on AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	);

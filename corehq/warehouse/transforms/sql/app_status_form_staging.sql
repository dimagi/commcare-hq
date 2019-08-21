INSERT INTO {{ app_status_form_staging }} (
       last_submission,
       submission_build_version,
       commcare_version,
       user_dim_id,
       app_dim_id,
       domain,
       batch_id
)

SELECT
    last_submission,
    submission_build_version,
    commcare_version,
    user_dim_id,
    app_dim_id,
    domain,
    '{{ batch_id }}'
FROM
(
SELECT
	row_number() over wnd,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_submission_date
	    ELSE  received_on
	END AS last_submission,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_app_build_version
            ELSE build.version::VARCHAR
	END AS submission_build_version,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_app_commcare_version
	    ELSE commcare_version
	END AS commcare_version,
	    user_dim.id as user_dim_id,
	    app_dim.id as app_dim_id,
	    form_staging.domain as domain
	FROM {{ form_staging }} as form_staging
	LEFT JOIN {{ user_dim }} as user_dim
	ON user_dim.user_id = form_staging.user_id
	LEFT JOIN {{ application_dim }} as app_dim
	ON form_staging.app_id = app_dim.application_id
	LEFT JOIN {{ application_dim }} as build
	ON form_staging.build_id = build.application_id
    LEFT JOIN {{ app_status_fact }} as app_status
	ON app_dim.id = app_status.app_dim_id and user_dim.id = app_status.user_dim_id
	WHERE form_staging.user_id <> '' and user_dim.doc_type='CommCareUser'
        WINDOW wnd AS (
            PARTITION BY user_dim.id, COALESCE(app_dim.id, -1) ORDER BY received_on AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)
) as form_data where row_number=1;

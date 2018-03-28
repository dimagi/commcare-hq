INSERT INTO {{ app_status_form_staging }} (
       last_submission,
       submission_build_version,
       commcare_version,
       user_id,
       app_id,
       domain,
       batch_id
)

SELECT
    last_submission,
    submission_build_version,
    commcare_version,
    user_id,
    app_id,
    domain,
    '{{ batch_id }}'
FROM
(
SELECT
	row_number() over wnd,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_submission_date
	    ELSE  first_value(received_on AT TIME ZONE 'UTC') OVER wnd
	END AS last_submission,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_app_build_version
            ELSE app_dim.version::VARCHAR
	END AS submission_build_version,
	CASE
	    WHEN received_on < app_status.last_form_submission_date
	    THEN app_status.last_form_app_commcare_version
	    ELSE commcare_version
	END AS commcare_version,
	    form_staging.user_id as user_id,
	    form_staging.app_id as app_id,
	    form_staging.domain as domain
	FROM {{ form_staging }} as form_staging
	LEFT JOIN {{ application_dim }} as app_dim
	ON form_staging.app_id = app_dim.application_id
	LEFT JOIN {{ app_status_fact }} as app_status
	ON form_staging.app_id = app_status.app_id and form_staging.user_id = app_status.user_id
        WINDOW wnd AS (
            PARTITION BY form_staging.user_id, form_staging.app_id ORDER BY received_on AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
	)
) as form_data where row_number=1;

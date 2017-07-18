SELECT * FROM
(

    SELECT
        max(last_submission) as last_submission,
        max(last_submission_id) as last_submission_id,
        user_id,
        app_id
    FROM (
        SELECT
            first_value(received_on AT TIME ZONE 'UTC') OVER wnd AS last_submission,
            first_value(form_id) OVER wnd AS last_submission_id,
            user_id,
            app_id
        FROM {{ form_staging }}
        WINDOW wnd AS (
            PARTITION BY user_id, app_id ORDER BY received_on DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
    ) as t
    GROUP BY user_id, app_id
) as form_table

 LEFT OUTER JOIN

(
    SELECT
        max(last_sync) as last_sync,
        max(user_id) as user_id,
        max(build_id) as build_id
    FROM (
        SELECT
            first_value(sync_date AT TIME ZONE 'UTC') OVER wnd AS last_sync,
            first_value(user_id) OVER wnd AS user_id,
            first_value(build_id) OVER wnd AS build_id
        FROM {{ synclog_staging }}
        WINDOW wnd AS (
            PARTITION BY user_id ORDER BY sync_date AT TIME ZONE 'UTC' DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
     ) as t
     GROUP BY user_id
) as sync_table

ON sync_table.user_id = form_table.user_id

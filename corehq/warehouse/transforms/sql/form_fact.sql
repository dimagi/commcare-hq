INSERT INTO {{ form_fact }} (
    form_id,
    domain,
    domain_dim_id,
    app_id,
    xmlns,
    user_id,
    user_dim_id,
    received_on,
    deleted_on,
    edited_on,
    build_id,
    state,
    last_modified,
    batch_id,
    time_end,
    time_start,
    commcare_version,
    app_version
)
SELECT
    form_id,
    domain_table.domain,
    domain_table.id,
    app_id,
    xmlns,
    user_table.user_id,
    user_table.id,
    received_on,
    deleted_on,
    edited_on,
    build_id,
    state,
    GREATEST(received_on, deleted_on, edited_on) AT TIME ZONE default_timezone,
    '{{ batch_id }}',
    time_end,
    time_start,
    commcare_version,
    app_version
FROM
    {{ form_staging }} AS form_table
JOIN {{ domain_dim }} AS domain_table ON form_table.domain = domain_table.domain
-- Allow forms to be inserted that do not have users in the UserDim
LEFT OUTER JOIN {{ user_dim }} AS user_table ON form_table.user_id = user_table.user_id
ON CONFLICT (form_id) DO UPDATE 
SET domain = EXCLUDED.domain,
    domain_dim_id = EXCLUDED.domain_dim_id,
    app_id = EXCLUDED.app_id,
    xmlns = EXCLUDED.xmlns,
    user_id = EXCLUDED.user_id,
    user_dim_id = EXCLUDED.user_dim_id,
    received_on = EXCLUDED.received_on,
    deleted_on = EXCLUDED.deleted_on,
    edited_on = EXCLUDED.edited_on,
    build_id = EXCLUDED.build_id,
    state = EXCLUDED.state,
    last_modified = EXCLUDED.last_modified,
    batch_id = EXCLUDED.batch_id;

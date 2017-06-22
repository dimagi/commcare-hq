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
    last_modified
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
    GREATEST(received_on, deleted_on, edited_on) AT TIME ZONE default_timezone
FROM
    {{ form_staging }} AS form_table
JOIN {{ domain_dim }} AS domain_table ON form_table.domain = domain_table.domain
-- Allow forms to be inserted that do not have users in the UserDim
LEFT OUTER JOIN {{ user_dim }} AS user_table ON form_table.user_id = user_table.user_id

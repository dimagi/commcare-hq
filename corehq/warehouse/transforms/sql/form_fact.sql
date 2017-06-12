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
    CASE
        WHEN
            (received_on > deleted_on OR deleted_on IS NULL) AND
            (received_on > edited_on OR edited_on IS NULL)
        THEN received_on::timestamp AT TIME ZONE default_timezone
        WHEN
            (deleted_on > received_on OR received_on IS NULL) AND
            (deleted_on > edited_on OR edited_on IS NULL)
        THEN deleted_on::timestamp AT TIME ZONE default_timezone
        ELSE edited_on::timestamp AT TIME ZONE default_timezone
    END
FROM
    {{ form_staging }} AS form_table
JOIN {{ domain_dim }} AS domain_table ON form_table.domain = domain_table.domain
-- TODO: Should we allow records to be inserted if not found in the UserDim? Unknown Users?
JOIN {{ user_dim }} AS user_table ON form_table.user_id = user_table.user_id

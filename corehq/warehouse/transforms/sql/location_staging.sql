INSERT INTO {{ location_staging }} (
    domain,
    name,
    site_code,
    location_id,
    external_id,
    supply_point_id,
    user_id,
    sql_location_id,
    sql_parent_location_id,
    location_last_modified,
    is_archived,
    latitude,
    longitude
)
SELECT
    domain,
    name,
    site_code,
    location_id,
    external_id,
    supply_point_id,
    user_id,
    id,
    parent_id,
    last_modified,
    is_archived,
    latitude,
    longitude
FROM
    {{ sqllocation_table }}
WHERE
    last_modified > '{{ start_datetime }}' AND
    last_modified <= '{{ end_datetime }}'

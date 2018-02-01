INSERT INTO {{ location_staging }} (
    domain,
    name,
    site_code,
    location_id,
    location_type_id,
    external_id,
    supply_point_id,
    user_id,
    sql_location_id,
    sql_parent_location_id,
    location_last_modified,
    location_created_on,
    is_archived,
    latitude,
    longitude,
    batch_id,
    location_type_name,
    location_type_code,
    location_type_last_modified
)
SELECT
    domain,
    name,
    site_code,
    location_id,
    location_type_id,
    external_id,
    supply_point_id,
    user_id,
    id,
    parent_id,
    last_modified,
    created_at,
    is_archived,
    latitude,
    longitude,
    lt.name,
    lt.code,
    lt.last_modified,
    '{{ batch_id }}'
FROM
    {{ sqllocation_table }} as location
INNER JOIN {{ location_type_table }} as lt
ON location.location_type_id = lt.id
WHERE
    (last_modified > '{{ start_datetime }}' AND
    last_modified <= '{{ end_datetime }}') OR
    (lt.last_modified > '{{ start_datetime }}' AND
    lt.last_modified <= '{{ end_datetime }}')

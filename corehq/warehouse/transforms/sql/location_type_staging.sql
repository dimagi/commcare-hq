INSERT INTO {{ location_type_staging }} (
    domain,
    name,
    code,
    location_type_id,
    location_type_last_modified,
    batch_id
)
SELECT
    domain,
    name,
    code,
    id,
    last_modified,
    '{{ batch_id }}'
FROM
    {{ locationtype_table }}
WHERE
    last_modified > '{{ start_datetime }}' AND
    last_modified <= '{{ end_datetime }}'

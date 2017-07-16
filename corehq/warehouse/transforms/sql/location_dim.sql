-- First insert all records into location dim from staging tables without foreign keys
INSERT INTO {{ location_dim }} (
    domain,

    location_id,
    sql_location_id,
    location_level_0,
    location_level_1,

    name,
    site_code,
    external_id,
    supply_point_id,
    is_archived,
    latitude,
    longitude,

    location_type_name,
    location_type_code,
    location_type_id,

    location_last_modified,
    location_created_on,

    dim_last_modified,
    dim_created_on,
    -- TODO: Figure out how to handle deletes when we actually hard deleted the model
    deleted,
    batch_id
)

SELECT
    l_table.domain,

    l_table.location_id,
    l_table.sql_location_id,
    l_table.sql_location_id,
    l_table.sql_parent_location_id,

    l_table.name,
    l_table.site_code,
    l_table.external_id,
    l_table.supply_point_id,
    l_table.is_archived,
    l_table.latitude,
    l_table.longitude,

    lt_table.name,
    lt_table.code,
    lt_table.location_type_id,

    l_table.location_last_modified,
    l_table.location_created_on,

    now(),
    now(),
    false,
    '{{ batch_id }}'
FROM
    {{ location_staging }} as l_table
INNER JOIN
    {{ location_type_staging }} as lt_table
ON l_table.location_type_id = lt_table.location_type_id AND l_table.domain = lt_table.domain;


-- After the join update all dims with their new foreign keys
UPDATE {{ location_dim }} AS location_dim_target

SET
    location_level_0 = l0.sql_location_id,
    location_level_1 = l1.sql_location_id,
    location_level_2 = l2.sql_location_id,
    location_level_3 = l3.sql_location_id,
    location_level_4 = l4.sql_location_id,
    location_level_5 = l5.sql_location_id,
    location_level_6 = l6.sql_location_id,
    location_level_7 = l7.sql_location_id,
    level = (
        CASE WHEN l0.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l1.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l2.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l3.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l4.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l5.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l6.sql_location_id IS NULL THEN 0 ELSE 1 END +
        CASE WHEN l7.sql_location_id IS NULL THEN 0 ELSE 1 END
    ) - 1

FROM {{ location_dim }} AS l0
LEFT JOIN {{ location_dim }} l1 ON l0.location_level_1 = l1.location_level_0
LEFT JOIN {{ location_dim }} l2 ON l1.location_level_1 = l2.location_level_0
LEFT JOIN {{ location_dim }} l3 ON l2.location_level_1 = l3.location_level_0
LEFT JOIN {{ location_dim }} l4 ON l3.location_level_1 = l4.location_level_0
LEFT JOIN {{ location_dim }} l5 ON l4.location_level_1 = l5.location_level_0
LEFT JOIN {{ location_dim }} l6 ON l5.location_level_1 = l6.location_level_0
LEFT JOIN {{ location_dim }} l7 ON l6.location_level_1 = l7.location_level_0

WHERE
    location_dim_target.sql_location_id = l0.sql_location_id;

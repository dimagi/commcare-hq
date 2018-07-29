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
    domain,

    location_id,
    sql_location_id,
    sql_location_id,
    sql_parent_location_id,

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

    now(),
    now(),
    false,
    '{{ batch_id }}'
FROM
    {{ location_staging }}
ON CONFLICT (location_id) DO UPDATE
SET domain = EXCLUDED.domain,
    sql_location_id = EXCLUDED.sql_location_id,
    location_level_0 = EXCLUDED.location_level_0,
    location_level_1 = EXCLUDED.location_level_1,
    name = EXCLUDED.name,
    site_code = EXCLUDED.site_code,
    external_id = EXCLUDED.external_id,
    supply_point_id = EXCLUDED.supply_point_id,
    is_archived = EXCLUDED.is_archived,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    location_type_name = EXCLUDED.location_type_name,
    location_type_code = EXCLUDED.location_type_code,
    location_type_id = EXCLUDED.location_type_id,
    location_last_modified = EXCLUDED.location_last_modified,
    location_created_on = EXCLUDED.location_created_on,
    dim_last_modified = EXCLUDED.dim_last_modified,
    deleted = EXCLUDED.deleted,
    batch_id = EXCLUDED.batch_id;


-- After the join update all dims with their new foreign keys
UPDATE {{ location_dim }} AS location_dim_target

SET
    location_level_0 = get_location_level_id(0, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_1 = get_location_level_id(1, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_2 = get_location_level_id(2, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_3 = get_location_level_id(3, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_4 = get_location_level_id(4, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_5 = get_location_level_id(5, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_6 = get_location_level_id(6, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
    location_level_7 = get_location_level_id(7, l0.sql_location_id, l1.sql_location_id,
                                            l2.sql_location_id, l3.sql_location_id, l4.sql_location_id,
                                            l5.sql_location_id, l6.sql_location_id, l7.sql_location_id),
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

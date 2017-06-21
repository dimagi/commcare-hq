INSERT INTO {{ location_dim }} (
    domain,

    location_id,
    sql_location_id,

    level,
    location_level_0,
    location_level_1,
    location_level_2,
    location_level_3,
    location_level_4,
    location_level_5,
    location_level_6,
    location_level_7,

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
    deleted
)
WITH RECURSIVE location_hierarchy(
    sql_location_id,
    level,
    location_path
) AS (
    -- Initially seed the recursive procedure
    SELECT
        sql_location_id,
        0,
        ARRAY[sql_location_id],
        -- Extra meta data
        name,
        domain,
        site_code,
        external_id,
        location_id,
        location_type_id,
        supply_point_id,
        is_archived,
        latitude,
        longitude,
        location_last_modified,
        location_created_on


    FROM
        {{ location_staging }}
    WHERE
        sql_parent_location_id is NULL

    UNION

    -- Join the working data on the staging table with its parent id
    SELECT
        l.sql_location_id,
        location_hierarchy.level + 1,
        ARRAY_APPEND(location_hierarchy.location_path, l.sql_location_id),

        -- Extra meta data
        l.name,
        l.domain,
        l.site_code,
        l.external_id,
        l.location_id,
        l.location_type_id,
        l.supply_point_id,
        l.is_archived,
        l.latitude,
        l.longitude,
        l.location_last_modified,
        l.location_created_on
    FROM
        {{ location_staging }} AS l
    INNER JOIN location_hierarchy ON location_hierarchy.sql_location_id = l.sql_parent_location_id
)
SELECT
    location_hierarchy.domain,

    location_hierarchy.location_id,
    location_hierarchy.sql_location_id,

    location_hierarchy.level,
    location_hierarchy.location_path[1],
    location_hierarchy.location_path[2],
    location_hierarchy.location_path[3],
    location_hierarchy.location_path[4],
    location_hierarchy.location_path[5],
    location_hierarchy.location_path[6],
    location_hierarchy.location_path[7],
    location_hierarchy.location_path[8],

    location_hierarchy.name,
    location_hierarchy.site_code,
    location_hierarchy.external_id,
    location_hierarchy.supply_point_id,
    location_hierarchy.is_archived,
    location_hierarchy.latitude,
    location_hierarchy.longitude,

    lt_table.name,
    lt_table.code,
    lt_table.location_type_id,

    location_hierarchy.location_last_modified,
    location_hierarchy.location_created_on,

    now(),
    now(),
    false
FROM
    location_hierarchy
INNER JOIN
    {{ location_type_staging }} as lt_table
ON location_hierarchy.location_type_id = lt_table.location_type_id AND location_hierarchy.domain = lt_table.domain

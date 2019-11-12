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
    location_level_2 = null,
    location_level_3 = null,
    location_level_4 = null,
    location_level_5 = null,
    location_level_6 = null,
    location_level_7 = null,
    level = null,
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
    dim_last_modified = EXCLUDED.dim_last_modified,
    deleted = EXCLUDED.deleted,
    batch_id = EXCLUDED.batch_id;


-- update level and parent hierarchy
UPDATE warehouse_locationdim dim SET
    level = cte.level,
    location_level_2 = cte.hierarchy[3],
    location_level_3 = cte.hierarchy[4],
    location_level_4 = cte.hierarchy[5],
    location_level_5 = cte.hierarchy[6],
    location_level_6 = cte.hierarchy[7],
    location_level_7 = cte.hierarchy[8]
FROM (
    WITH RECURSIVE location_cte (batch_id, sql_location_id, level, parent_key, hierarchy)
    AS (
        SELECT
            batch_id,
            sql_location_id,
            0,
            NULL::INTEGER,
            ARRAY[sql_location_id]
        FROM warehouse_locationdim
        WHERE location_level_1 IS NULL
        UNION ALL
        SELECT
            child.batch_id,
            child.sql_location_id,
            parent.level+1,
            child.location_level_1,
            ARRAY[child.sql_location_id] || parent.hierarchy
        FROM location_cte parent
        JOIN warehouse_locationdim child ON child.location_level_1 = parent.sql_location_id
    )
    SELECT * FROM location_cte WHERE batch_id = {{ batch_id }}
) cte
WHERE cte.sql_location_id = dim.sql_location_id;

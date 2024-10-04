DROP FUNCTION IF EXISTS get_case_owning_locations(TEXT, INTEGER[]);

CREATE FUNCTION get_case_owning_locations(
    domain_name TEXT,
    -- array of locations_sqllocation.id (NOT locations_sqllocation.location_id)
    user_location_ids_array INTEGER[]
) RETURNS TABLE (
    "id" INTEGER
) AS $$
BEGIN
    /*
        Gets the locations whose cases belong in the user's restore file. Spin-off of the function
        `get_location_fixture_ids`--this function follows the same sort of high-level process with a slightly
        different approach.

        1. (expand_to CTE) Gets the expand_to location types for each of the user's locations and, using
        recursion, their depths
        2. (expand_from CTE) Turns expand_to into a table of the user's location IDs, their depths, and
        the depths to expand to (-2 for unlimited expansion)
        3. (restore_file_locations CTE) Gets appropriate set of locations using the columns from #2
        4. (final select statement) Gets _distinct_ set of location IDs whose type has case sharing on
    */

    RETURN QUERY

    WITH RECURSIVE expand_to AS (
        /*
            Get the expand_to types for each of the user's locations, and their depths.
        */

        WITH RECURSIVE cte AS (
            SELECT
                expand_to_type."parent_type_id",
                0 AS "depth",
                expand_to_type."id" AS "expand_to_type"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type
                ON loc."location_type_id" = loc_type."id"
            INNER JOIN "locations_locationtype" expand_to_type
                ON expand_to_type."id" = loc_type."expand_view_child_data_to_id"
            WHERE
                loc."id" = ANY(user_location_ids_array)
                AND loc_type."expand_view_child_data_to_id" IS NOT NULL
                AND loc_type."view_descendants" = TRUE

            UNION ALL

            SELECT
                loc_type."parent_type_id",
                "cte"."depth" + 1 AS "depth",
                "cte"."expand_to_type" AS "expand_to_type"
            FROM "locations_locationtype" loc_type
            INNER JOIN "cte" ON loc_type."id" = "cte"."parent_type_id"
        )

        SELECT
            "cte"."expand_to_type",
            MAX("cte"."depth") AS "expand_to_depth"
        FROM "cte"
        WHERE "cte"."parent_type_id" IS NULL
        GROUP BY "cte"."expand_to_type"

    ), expand_from AS (
        /*
            This CTE has the columns:

            Location ID, depth for location to expand to, and depth of location itself (in that order).

            Each row is a location the user belongs to. This info is then used by the restore_file_locations
            CTE to get the list of expanded locations.
        */

        WITH RECURSIVE cte AS (

            -- Get location ID and depth to expand to. Recursion base case
            SELECT
                loc_type."parent_type_id" AS "recur_parent_type_id",
                0 as "recur_depth",
                loc."id" AS "loc_id",
                CASE WHEN loc_type."expand_view_child_data_to_id" IS NULL THEN -2
                    ELSE (
                        SELECT "expand_to_depth"
                        FROM "expand_to"
                        WHERE "expand_to_type" = loc_type."expand_view_child_data_to_id"
                    )
                END AS "expand_to_depth"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type ON loc."location_type_id" = loc_type."id"
            WHERE
                loc."is_archived" = FALSE
                AND loc."domain" = domain_name
                AND loc."id" = ANY(user_location_ids_array)
                AND loc_type."view_descendants" = TRUE

            UNION ALL

            -- Recursion to get depth of each location
            SELECT
                loc_type."parent_type_id" AS "recur_parent_type_id",
                "cte"."recur_depth" + 1 AS "recur_depth",
                "cte"."loc_id",
                "cte"."expand_to_depth"
            FROM "locations_locationtype" loc_type
            INNER JOIN "cte" ON loc_type."id" = "cte"."recur_parent_type_id"

        )

        -- All info is available at top-level node
        SELECT
            "cte"."loc_id",
            "cte"."expand_to_depth",
            "cte"."recur_depth" AS "loc_depth"
        FROM "cte"
        WHERE "cte"."recur_parent_type_id" IS NULL

    ), restore_file_locations AS (

        SELECT
            loc."id",
            "expand_from"."loc_depth",
            loc."location_type_id"
        FROM "locations_sqllocation" loc
        INNER JOIN "expand_from" on loc."id" = "expand_from"."loc_id"
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name

        UNION ALL

        SELECT
            loc."id",
            "restore_file_locations"."loc_depth" + 1 AS "loc_depth",
            loc."location_type_id"
        FROM "locations_sqllocation" loc
        INNER JOIN "restore_file_locations" ON loc."parent_id" = "restore_file_locations"."id"
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name
            AND EXISTS (
                SELECT 1
                FROM "expand_from" xf
                WHERE
                    (
                        xf."expand_to_depth" = -2  -- expansion depth is unlimited
                        OR "restore_file_locations"."loc_depth" < xf."expand_to_depth"
                    )
            )
    )

    -- Final SELECT. Filter by "shares cases" setting
    SELECT DISTINCT
        x."id"
    FROM "restore_file_locations" x
    INNER JOIN "locations_locationtype" loc_type ON x."location_type_id" = loc_type."id"
    WHERE loc_type."shares_cases" = TRUE

    UNION ALL

    -- And union with the user's locations who can't view descendants
    SELECT
        loc."id"
    FROM "locations_sqllocation" loc
    INNER JOIN "locations_locationtype" loc_type on loc."location_type_id" = loc_type."id"
    WHERE loc."id" = ANY(user_location_ids_array)
        AND loc_type."view_descendants" = FALSE
        AND loc_type."shares_cases" = TRUE;

END;
$$ LANGUAGE plpgsql;

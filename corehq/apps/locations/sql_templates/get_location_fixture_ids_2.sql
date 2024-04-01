DROP FUNCTION IF EXISTS get_location_fixture_ids_2(TEXT, INTEGER[]);

CREATE FUNCTION get_location_fixture_ids_2(
    domain_name TEXT,
    -- array of locations_sqllocation.id (NOT locations_sqllocation.location_id)
    user_location_ids_array INTEGER[],
    case_sync_restriction BOOLEAN
) RETURNS TABLE (
    "id" INTEGER,       -- location id
    "path" INTEGER[],   -- location tree path from root (array of location ids)
    "depth" INTEGER     -- depth in locations tree (0 is root node)
) AS $$
BEGIN
    /*
    Get fixture locations using expand_from criteria

    There may be ambiguities in location type configurations that could
    cause undefined outcomes:
    - expand_from_root = TRUE seems to do the same thing as
      include_without_expanding IS NOT NULL (redundant config?).
    - expand_from_root = TRUE with expand_from IS NOT NULL seems logically
      inconsistent. Suggest adding check constraint to prevent this state.
    - include_without_expanding IS NOT NULL with expand_from IS NOT NULL
      seems logically inconsistent. Suggest adding check constraint.
    - expand_from could point to a location that is not an ancester
    - expand_to could point to a location that is not a descendant (maybe
      doesn't matter since it's only used to calculate a depth).
    - two location types along the same path could both have expand_to set
      to different levels, making the expansion depth ambiguous if a user
      had both of those locations.
    - ancestors could be excluded with improper include_only config.
      seems like we could achieve the same thing with expand_from/expand_to
    */

    RETURN QUERY

    WITH RECURSIVE expand_to AS (
        /*
        CTE with location type ids and corresponding expand to depths

        This traverses the location type hierarchy, which is assumed to
        mirror the location hierarchy but contain many less records. The
        traversal is over user locations' types and their ancestors, so
        should be reasonably fast.

        "expand_to" columns:
        - expand_to_type: location type id, -1 if include_without_expanding
        - expand_to_depth: expansion depth
        */

        WITH RECURSIVE cte AS (
            -- get expand_to location types
            SELECT
                expand_to_type."parent_type_id",
                0 AS "depth",
                expand_to_type."id" AS "expand_to_type"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type
                ON loc."location_type_id" = loc_type."id"
            INNER JOIN "locations_locationtype" expand_to_type
                ON CASE
                    WHEN case_sync_restriction THEN expand_to_type."id" = loc_type."restrict_cases_to_id"
                    ELSE expand_to_type."id" = loc_type."expand_to_id"
                END
            WHERE
                loc."id" = ANY(user_location_ids_array)
                AND CASE
                    WHEN case_sync_restriction THEN loc_type."restrict_cases_to_id" IS NOT NULL
                    ELSE loc_type."expand_to_id" IS NOT NULL
                END


            UNION ALL

            -- get include_without_expanding location types
            SELECT
                iwe_type."parent_type_id",
                0 AS "depth",
                -1 AS "expand_to_type"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type
                ON loc."location_type_id" = loc_type."id"
            INNER JOIN "locations_locationtype" iwe_type
                ON loc_type."include_without_expanding_id" = iwe_type."id"
            WHERE
                NOT case_sync_restriction
                AND loc."id" = ANY(user_location_ids_array)
                AND loc_type."include_without_expanding_id" IS NOT NULL

            UNION ALL

            -- recursive query to calculate depths
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
        WHERE "cte"."parent_type_id" IS NULL  -- exclude all but the root items
        GROUP BY "cte"."expand_to_type"

    ), expand_from AS (
        /*
        CTE with expand from location ids and expansion depths

        The traversal is over user locations and their ancestors, so should
        be reasonably fast.

        "expand_from" columns:
        - loc_id: location id, null for include_without_expanding or
          expand_from_root.
        - depth: expand to depth. Negative values in this column have
          special meanings. See output examples below.

         loc_id | depth
        --------|-------
         NULL   |  3     -- include all locations with depth <= 3
         1      |  4     -- include all descendents of location 1 to depth 4
         10     | -1     -- include location 10 (but do not expand)
         100    | -2     -- include all descendents of location 100, unlimited depth
         11     | -3     -- location 11 and its descendants are included based on
                            include_only types
        */

        WITH RECURSIVE cte AS (
            -- get include_without_expanding depth
            SELECT
                NULL AS "parent_id",
                NULL AS "expand_from_type",
                NULL AS "loc_id",
                "expand_to"."expand_to_depth" AS "depth"
            FROM "expand_to"
            WHERE "expand_to"."expand_to_type" = -1

            UNION ALL

            SELECT
                loc."parent_id",
                CASE
                    WHEN (
                        -- if expand_from is set and not the current location type
                        -- it will be one of this location's ancestors
                        loc_type."expand_from" IS NOT NULL
                        AND loc_type."expand_from_root" = FALSE
                        AND loc_type."expand_from" <> loc."location_type_id"
                        AND NOT EXISTS (
                            -- might be wrong to ignore loc_type.expand_from
                            -- when include_only types exist
                            SELECT 1
                            FROM "locations_locationtype_include_only"
                            WHERE "from_locationtype_id" = loc."location_type_id"
                        )
                    ) AND NOT case_sync_restriction THEN loc_type."expand_from"
                    -- otherwise it will be null for this and all ancestors
                    ELSE NULL
                END AS "expand_from_type",
                CASE
                    -- expand_from_root -> no path
                    WHEN loc_type."expand_from_root" = TRUE AND NOT case_sync_restriction THEN NULL
                    -- else first path element
                    ELSE loc."id"
                END AS "loc_id",
                CASE
                    WHEN case_sync_restriction THEN (
                        SELECT "expand_to_depth"
                        FROM "expand_to"
                        WHERE "expand_to_type" = loc_type."restrict_cases_to_id"
                    )
                    -- get expand_to depth
                    WHEN loc_type."expand_to_id" IS NOT NULL THEN (
                        SELECT "expand_to_depth"
                        FROM "expand_to"
                        WHERE "expand_to_type" = loc_type."expand_to_id"
                    )
                    -- use include_only types
                    WHEN EXISTS (
                        SELECT 1
                        FROM "locations_locationtype_include_only"
                        WHERE "from_locationtype_id" = loc."location_type_id"
                    ) AND NOT case_sync_restriction THEN -3
                    -- else unlimited expansion depth
                    ELSE -2
                END AS "depth"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type ON loc."location_type_id" = loc_type."id"
            WHERE
                loc."is_archived" = FALSE
                AND loc."domain" = domain_name
                AND loc."id" = ANY(user_location_ids_array)

            UNION ALL

            SELECT
                loc."parent_id",
                CASE
                    -- set expand_from_type if it will apply to an ancestor
                    WHEN "cte"."expand_from_type" <> loc."location_type_id"
                    THEN "cte"."expand_from_type"
                    -- otherwise it will be null for this and all ancestors
                    ELSE NULL
                END AS "expand_from_type",
                CASE
                    -- expand_from_root -> no path
                    WHEN "cte"."loc_id" IS NULL THEN NULL
                    -- else next element of path
                    ELSE loc."id"
                END AS "loc_id",
                CASE
                    -- ancestor of expand_from -> include but do not expand
                    WHEN (
                        "cte"."loc_id" IS NOT NULL
                        AND "cte"."expand_from_type" IS NULL
                    ) THEN -1
                    -- else no path yet or starting path -> use previous depth
                    ELSE "cte"."depth"
                END AS "depth"
            FROM "locations_sqllocation" loc
            INNER JOIN "cte" ON loc."id" = "cte"."parent_id"
            WHERE loc."is_archived" = FALSE
        )

        SELECT DISTINCT "cte"."loc_id", "cte"."depth" FROM "cte"

    ), fixture_ids AS (
        /*
        Get fixture locations using expand_from criteria

        "fixture_ids" columns:
        - id: location id
        - path: location tree path from root (array of location ids)
        - depth: depth in locations tree (0 is root node)
        */

        SELECT
            loc."id",
            ARRAY[loc."id"] AS "path",
            0 AS "depth"
        FROM "locations_sqllocation" loc
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name
            AND loc."parent_id" IS NULL
            AND EXISTS (
                SELECT 1
                FROM "expand_from" xf
                WHERE
                    (
                        "loc_id" = loc."id" AND (
                            xf."depth" = -1     -- ancestor of expand_from
                            OR xf."depth" = -2  -- expansion depth is unlimited
                            -- descendant of expand_from within expand_to depth
                            OR xf."depth" >= 0
                        )
                    ) OR (
                        -- include_without_expanding/expand_from_root
                        -- AND
                        -- unlimited depth or max depth >= current depth
                        "loc_id" IS NULL AND (xf."depth" = -2 OR xf."depth" >= 0)
                    ) OR (
                        -- location type is in include_only types
                        xf."depth" = -3
                        AND "loc_id" = loc."id"
                        AND loc."location_type_id" IN (
                            SELECT to_locationtype_id
                            FROM locations_locationtype_include_only
                            INNER JOIN "locations_sqllocation" x
                                ON x."location_type_id" = from_locationtype_id
                            WHERE x."id" = ANY(user_location_ids_array)
                        )
                    )
            )

        UNION ALL

        SELECT
            loc."id",
            array_append("fixture_ids"."path", loc."id") AS "path",
            "fixture_ids"."depth" + 1 AS "depth"
        FROM "locations_sqllocation" loc
        INNER JOIN "fixture_ids" ON loc."parent_id" = "fixture_ids"."id"
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name
            AND EXISTS (
                SELECT 1
                FROM "expand_from" xf
                WHERE
                    (
                        "loc_id" = loc."id" AND (
                            xf."depth" = -1     -- ancestor of expand_from
                            OR xf."depth" = -2  -- expansion depth is unlimited
                            -- descendant of expand_from within expand_to depth
                            OR "fixture_ids"."depth" < xf."depth"
                        )
                    ) OR (
                        (
                            -- include_without_expanding/expand_from_root or
                            -- descendant of expand_from within expand_to depth
                            "loc_id" IS NULL OR "loc_id" = ANY("fixture_ids"."path")
                        ) AND (
                            xf."depth" = -2  -- expansion depth is unlimited
                            -- descendant of expand_from within expand_to depth
                            OR "fixture_ids"."depth" < xf."depth"
                        )
                    ) OR (
                        -- location type is in include_only types
                        xf."depth" = -3 AND (
                            "loc_id" = loc."id"
                            OR "loc_id" = ANY("fixture_ids"."path")
                        ) AND loc."location_type_id" IN (
                            SELECT to_locationtype_id
                            FROM locations_locationtype_include_only
                            INNER JOIN "locations_sqllocation" x
                                ON x."location_type_id" = from_locationtype_id
                            WHERE x."id" = ANY(user_location_ids_array)
                        )
                    )
            )
    )

    SELECT x."id", x."path", x."depth" from fixture_ids x;

END;
$$ LANGUAGE plpgsql;

DROP FUNCTION IF EXISTS get_location_fixture_ids(TEXT, INTEGER[]);

CREATE FUNCTION get_location_fixture_ids(
    domain_name TEXT,
    -- array of locations_sqllocation.id (NOT locations_sqllocation.location_id)
    user_location_ids_array INTEGER[]
) RETURNS TABLE (
    "id" INTEGER,
    "path" INTEGER[],
    "depth" INTEGER
) AS $$
BEGIN
    RETURN QUERY

    WITH RECURSIVE expand_to AS (
        WITH RECURSIVE cte AS (
            SELECT
                expand_to_type."parent_type_id",
                0 AS "depth",
                expand_to_type."id" AS "expand_to_type"
            FROM "locations_sqllocation" loc
            INNER JOIN "locations_locationtype" loc_type
                ON loc."location_type_id" = loc_type."id"
            INNER JOIN "locations_locationtype" expand_to_type
                ON expand_to_type."id" = loc_type."expand_to_id"
            WHERE
                loc."id" = ANY(user_location_ids_array)
                AND loc_type."expand_to_id" IS NOT NULL

            UNION ALL

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
                loc."id" = ANY(user_location_ids_array)
                AND loc_type."include_without_expanding_id" IS NOT NULL

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
        WITH RECURSIVE cte AS (
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
                        loc_type."expand_from_root" = FALSE
                        AND loc_type."expand_from" IS NOT NULL
                        AND NOT (
                            loc_type."expand_from" = loc."location_type_id"
                            AND loc_type."expand_from" IS NOT NULL
                        )
                        AND NOT EXISTS (
                            SELECT 1
                            FROM "locations_locationtype" U0
                            INNER JOIN "locations_locationtype_include_only" U1 ON U0."id" = U1."to_locationtype_id"
                            WHERE U1."from_locationtype_id" = loc."location_type_id"
                        )
                    )
                    THEN loc_type."expand_from"
                    ELSE NULL
                END AS "expand_from_type",
                CASE
                    WHEN loc_type."expand_from_root" = TRUE THEN NULL
                    ELSE loc."id"
                END AS "loc_id",
                CASE
                    WHEN loc_type."expand_to_id" IS NOT NULL THEN (
                        SELECT U0."expand_to_depth"
                        FROM "expand_to" U0
                        WHERE U0."expand_to_type" = loc_type."expand_to_id"
                    )
                    WHEN EXISTS (
                        SELECT 1
                        FROM "locations_locationtype" U0
                        INNER JOIN "locations_locationtype_include_only" U1
                            ON U0."id" = U1."to_locationtype_id"
                        WHERE U1."from_locationtype_id" = loc."location_type_id"
                    )
                    THEN -3
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
                    WHEN (
                        "cte"."expand_from_type" IS NOT NULL
                        AND "cte"."expand_from_type" <> loc."location_type_id"
                    )
                    THEN "cte"."expand_from_type"
                    ELSE NULL
                END AS "expand_from_type",
                CASE
                    WHEN "cte"."loc_id" IS NULL THEN NULL
                    ELSE loc."id"
                END AS "loc_id",
                CASE
                    WHEN (
                        "cte"."loc_id" IS NOT NULL
                        AND "cte"."expand_from_type" IS NULL
                    )
                    THEN -1
                    ELSE "cte"."depth"
                END AS "depth"
            FROM "locations_sqllocation" loc
            INNER JOIN "cte" ON loc."id" = "cte"."parent_id"
            WHERE loc."is_archived" = FALSE
        )

        SELECT DISTINCT "cte"."loc_id", "cte"."depth" FROM "cte"

    ), fixture_ids AS (
        SELECT
            loc."id",
            loc."parent_id",
            ARRAY[loc."id"] AS "path",
            0 AS "depth"
        FROM "locations_sqllocation" loc
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name
            AND loc."parent_id" IS NULL
            AND EXISTS (
                SELECT 1
                FROM "expand_from" U0
                WHERE
                    (
                        (
                            U0."depth" = -1
                            OR U0."depth" = -2
                            OR U0."depth" >= 0
                        )
                        AND U0."loc_id" = loc."id"
                    ) OR (
                        (
                            U0."depth" = -2
                            OR U0."depth" >= 0
                        ) AND (
                            U0."loc_id" IS NULL
                            OR U0."loc_id" = loc."id"
                        )
                    ) OR (
                        (
                            U0."loc_id" = loc."id"
                            OR U0."loc_id" = loc."id"
                        )
                        AND U0."depth" = -3
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
            loc."parent_id",
            array_append("fixture_ids"."path", loc."id") AS "path",
            "fixture_ids"."depth" + 1 AS "depth"
        FROM "locations_sqllocation" loc
        INNER JOIN "fixture_ids" ON loc."parent_id" = "fixture_ids"."id"
        WHERE
            loc."is_archived" = FALSE
            AND loc."domain" = domain_name
            AND EXISTS (
                SELECT 1
                FROM "expand_from" U0
                WHERE
                    (
                        (
                            U0."depth" = -1
                            OR U0."depth" = -2
                            OR U0."depth" >= "fixture_ids"."depth" + 1
                        )
                        AND U0."loc_id" = loc."id"
                    ) OR (
                        (
                            U0."depth" = -2
                            OR U0."depth" >= "fixture_ids"."depth" + 1
                        ) AND (
                            U0."loc_id" IS NULL
                            OR U0."loc_id" = ANY("fixture_ids"."path")
                        )
                    ) OR (
                        U0."depth" = -3 AND
                        (
                            U0."loc_id" = loc."id"
                            OR U0."loc_id" = ANY("fixture_ids"."path")
                        )
                        AND loc."location_type_id" IN (
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

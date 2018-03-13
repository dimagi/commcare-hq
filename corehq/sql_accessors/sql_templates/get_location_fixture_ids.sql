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
            (
                (
                    SELECT
                        "locations_locationtype"."parent_type_id",
                        0 AS "depth",
                        "locations_locationtype"."id" AS "expand_to_type"
                    FROM "locations_locationtype"
                    WHERE "locations_locationtype"."id" IN (
                        SELECT U1."expand_to_id"
                        FROM "locations_sqllocation" U0
                        INNER JOIN "locations_locationtype" U1 ON (U0."location_type_id" = U1."id")
                        WHERE (
                            U0."id" = ANY(user_location_ids_array)
                            AND U1."expand_to_id" IS NOT NULL
                        )
                    )
                )

                UNION ALL

                (
                    SELECT
                        "locations_locationtype"."parent_type_id",
                        0 AS "depth",
                        -1 AS "expand_to_type"
                    FROM "locations_locationtype"
                    WHERE "locations_locationtype"."id" IN (
                        SELECT U1."include_without_expanding_id"
                        FROM "locations_sqllocation" U0
                        INNER JOIN "locations_locationtype" U1 ON (U0."location_type_id" = U1."id")
                        WHERE (
                            U0."id" = ANY(user_location_ids_array)
                            AND U1."include_without_expanding_id" IS NOT NULL
                        )
                    )
                )
            )

            UNION ALL

            (
                SELECT
                    "locations_locationtype"."parent_type_id",
                    ("cte"."depth" + 1) AS "depth",
                    "cte"."expand_to_type" AS "expand_to_type"
                FROM "locations_locationtype", "cte"
                WHERE "locations_locationtype"."id" = ("cte"."parent_type_id")
            )
        )

        SELECT
            "cte"."expand_to_type",
            MAX("cte"."depth") AS "expand_to_depth"
        FROM "cte"
        WHERE "cte"."parent_type_id" IS NULL
        GROUP BY "cte"."expand_to_type"
    ), expand_from AS (
        WITH RECURSIVE cte AS (
            (
                (
                    SELECT
                        NULL AS "parent_id",
                        NULL AS "expand_from_type",
                        NULL AS "loc_id",
                        "expand_to"."expand_to_depth" AS "depth"
                    FROM "expand_to"
                    WHERE "expand_to"."expand_to_type" = -1
                )

                UNION ALL

                (
                    SELECT
                        "locations_sqllocation"."parent_id",
                        CASE 
                            WHEN (
                                "locations_locationtype"."expand_from_root" = (False)
                                AND "locations_locationtype"."expand_from" IS NOT NULL
                                AND NOT (
                                    "locations_locationtype"."expand_from" = ("locations_sqllocation"."location_type_id")
                                    AND "locations_locationtype"."expand_from" IS NOT NULL
                                )
                                AND EXISTS (
                                    SELECT 1
                                    FROM "locations_locationtype" U0
                                    INNER JOIN "locations_locationtype_include_only" U1 ON (U0."id" = U1."to_locationtype_id")
                                    WHERE U1."from_locationtype_id" = ("locations_sqllocation"."location_type_id")
                                ) = False
                            )
                            THEN "locations_locationtype"."expand_from"
                            ELSE NULL
                        END AS "expand_from_type",
                        CASE 
                            WHEN "locations_locationtype"."expand_from_root" = (True) THEN NULL
                            ELSE "locations_sqllocation"."id"
                        END AS "loc_id",
                        CASE 
                            WHEN "locations_locationtype"."expand_to_id" IS NOT NULL THEN (
                                SELECT U0."expand_to_depth"
                                FROM "expand_to" U0
                                WHERE U0."expand_to_type" = ("locations_locationtype"."expand_to_id")
                            )
                            WHEN EXISTS (
                                SELECT 1
                                FROM "locations_locationtype" U0
                                INNER JOIN "locations_locationtype_include_only" U1 ON (U0."id" = U1."to_locationtype_id")
                                WHERE U1."from_locationtype_id" = ("locations_sqllocation"."location_type_id")
                            ) = True
                            THEN -3
                            ELSE -2
                        END AS "depth"
                    FROM "locations_sqllocation"
                    INNER JOIN "locations_locationtype" ON ("locations_sqllocation"."location_type_id" = "locations_locationtype"."id")
                    WHERE (
                        "locations_sqllocation"."is_archived" = False
                        AND "locations_sqllocation"."domain" = domain_name
                        AND "locations_sqllocation"."id" IN (
                            SELECT U0."id"
                            FROM "locations_sqllocation" U0
                            WHERE U0."id" = ANY(user_location_ids_array)
                        )
                    )
                )
            )

            UNION ALL

            (
                SELECT
                    "locations_sqllocation"."parent_id",
                    CASE 
                        WHEN (
                            "cte"."expand_from_type" IS NOT NULL
                            AND NOT ("cte"."expand_from_type" = ("locations_sqllocation"."location_type_id"))
                        )
                        THEN "cte"."expand_from_type"
                        ELSE NULL
                    END AS "expand_from_type",
                    CASE 
                        WHEN "cte"."loc_id" IS NULL THEN NULL
                        ELSE "locations_sqllocation"."id"
                    END AS "loc_id",
                    CASE 
                        WHEN (
                            "cte"."loc_id" IS NOT NULL
                            AND "cte"."expand_from_type" IS NULL
                        )
                        THEN -1
                        ELSE "cte"."depth"
                    END AS "depth"
                FROM "locations_sqllocation", "cte"
                WHERE (
                    "locations_sqllocation"."is_archived" = False
                    AND "locations_sqllocation"."id" = ("cte"."parent_id")
                )
            )
        )

        SELECT DISTINCT "cte"."loc_id", "cte"."depth" FROM "cte"
    ), fixture_ids AS (
        (
            SELECT
                "locations_sqllocation"."id",
                "locations_sqllocation"."parent_id",
                Array ["locations_sqllocation"."id"] AS "path",
                0 AS "depth"
            FROM "locations_sqllocation"
            WHERE (
                "locations_sqllocation"."is_archived" = False
                AND EXISTS (
                    SELECT 1
                    FROM "expand_from" U0
                    WHERE (
                        (
                            (
                                U0."depth" = -1
                                OR U0."depth" = -2
                                OR U0."depth" >= (0)
                            )
                            AND U0."loc_id" = (("locations_sqllocation"."id"))
                        ) OR (
                            (
                                U0."depth" = -2
                                OR U0."depth" >= (0)
                            ) AND (
                                U0."loc_id" IS NULL
                                OR U0."loc_id" = ANY ((Array [("locations_sqllocation"."id")]))
                            )
                        ) OR (
                            (
                                U0."loc_id" = (("locations_sqllocation"."id"))
                                OR U0."loc_id" = ANY ((Array [("locations_sqllocation"."id")]))
                            )
                            AND ("locations_sqllocation"."location_type_id") IN (
                                (
                                    SELECT to_locationtype_id
                                    FROM locations_locationtype_include_only
                                    WHERE from_locationtype_id IN (
                                        SELECT "locations_sqllocation"."location_type_id"
                                        FROM "locations_sqllocation"
                                        WHERE "locations_sqllocation"."id" = ANY(user_location_ids_array)
                                    )
                                )
                            )
                            AND U0."depth" = -3
                        )
                    )
                ) = True
                AND "locations_sqllocation"."domain" = domain_name
                AND "locations_sqllocation"."parent_id" IS NULL
            )
        )

        UNION ALL

        (
            SELECT
                "locations_sqllocation"."id",
                "locations_sqllocation"."parent_id",
                array_append("fixture_ids"."path", "locations_sqllocation"."id") AS "path",
                ("fixture_ids"."depth" + 1) AS "depth"
            FROM "locations_sqllocation", "fixture_ids"
            WHERE (
                "locations_sqllocation"."is_archived" = False
                AND "locations_sqllocation"."parent_id" = ("fixture_ids"."id")
                AND EXISTS (
                    SELECT 1
                    FROM "expand_from" U0
                    WHERE (
                        (
                            (
                                U0."depth" = -1
                                OR U0."depth" = -2
                                OR U0."depth" >= (("fixture_ids"."depth" + 1))
                            )
                            AND U0."loc_id" = (("locations_sqllocation"."id"))
                        ) OR (
                            (
                                U0."depth" = -2
                                OR U0."depth" >= (("fixture_ids"."depth" + 1))
                            ) AND (
                                U0."loc_id" IS NULL
                                OR U0."loc_id" = ANY ((array_append("fixture_ids"."path", ("locations_sqllocation"."id"))))
                            )
                        ) OR (
                            (
                                U0."loc_id" = (("locations_sqllocation"."id"))
                                OR U0."loc_id" = ANY ((array_append("fixture_ids"."path", ("locations_sqllocation"."id"))))
                            )
                            AND ("locations_sqllocation"."location_type_id") IN (
                                (
                                    SELECT to_locationtype_id
                                    FROM locations_locationtype_include_only
                                    WHERE from_locationtype_id IN (
                                        SELECT "locations_sqllocation"."location_type_id"
                                        FROM "locations_sqllocation"
                                        WHERE "locations_sqllocation"."id" = ANY(user_location_ids_array)
                                    )
                                )
                            )
                            AND U0."depth" = -3
                        )
                    )
                ) = True
                AND "locations_sqllocation"."domain" = domain_name
            )
        )
    )

    SELECT x."id", x."path", x."depth" from fixture_ids x;

END;
$$ LANGUAGE plpgsql;
